"""Pipeline status and SSE streaming routes (NFR-USA-003)."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from colette.api.deps import CurrentUser, get_db, get_pipeline_runner, get_settings, require_role
from colette.api.schemas import PipelineSSEEvent, PipelineStatusResponse
from colette.config import Settings
from colette.db.repositories import PipelineRunRepository
from colette.orchestrator.event_bus import EventType
from colette.orchestrator.runner import PipelineRunner
from colette.security.rbac import Permission

router = APIRouter()

_TERMINAL_EVENTS = frozenset({EventType.PIPELINE_COMPLETED, EventType.PIPELINE_FAILED})


@router.get(
    "/projects/{project_id}/pipeline",
    response_model=PipelineStatusResponse,
)
async def get_pipeline_status(
    project_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(require_role(Permission.VIEW_PROJECT))],
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PipelineStatusResponse:
    """Get the latest pipeline run for a project."""
    repo = PipelineRunRepository(db)
    run = await repo.get_active_for_project(project_id)
    if run is None:
        # Try to find the most recent run (may be completed).
        runs = await repo.list_for_project(project_id, limit=1)
        if not runs:
            raise HTTPException(status_code=404, detail="No pipeline run found")
        run = runs[0]

    return PipelineStatusResponse(
        id=run.id,
        project_id=run.project_id,
        thread_id=run.thread_id,
        status=run.status,
        current_stage=run.current_stage,
        total_tokens=run.total_tokens,
        started_at=run.started_at,
        completed_at=run.completed_at,
        state_snapshot=run.state_snapshot,
    )


def _make_sse_payload(event_type: str, project_id: str, **kwargs: object) -> str:
    """Build a single SSE frame from the given fields."""
    payload = PipelineSSEEvent(
        event_type=event_type,
        project_id=project_id,
        timestamp=kwargs.pop("timestamp", datetime.now(UTC).isoformat()),  # type: ignore[arg-type]
        **kwargs,  # type: ignore[arg-type]
    )
    return f"event: {event_type}\ndata: {payload.model_dump_json()}\n\n"


async def _emit_catchup_events(project_id: str, runner: PipelineRunner) -> AsyncGenerator[str]:
    """Emit synthetic events for stages that already progressed.

    Since LangGraph only checkpoints AFTER a node completes, the
    checkpoint's ``stage_statuses`` may still say "pending" for the
    current running stage.  We infer state from ``is_active`` +
    ``progress.stage``: stages before the current one are completed,
    the current one is running.
    """
    from colette.orchestrator.state import STAGE_ORDER

    try:
        progress = await runner.get_progress(project_id)
    except Exception:  # best-effort catch-up
        return

    try:
        current_idx = STAGE_ORDER.index(progress.stage)
    except ValueError:
        return

    ts = datetime.now(UTC).isoformat()
    for i, stage_name in enumerate(STAGE_ORDER):
        if i < current_idx:
            yield _make_sse_payload(
                "stage_started",
                project_id,
                stage=stage_name,
                timestamp=ts,
            )
            yield _make_sse_payload(
                "stage_completed",
                project_id,
                stage=stage_name,
                timestamp=ts,
                elapsed_seconds=progress.elapsed_seconds,
            )
        elif i == current_idx:
            yield _make_sse_payload(
                "stage_started",
                project_id,
                stage=stage_name,
                timestamp=ts,
            )


async def _sse_event_generator(
    project_id: str,
    runner: PipelineRunner,
    heartbeat_seconds: float,
) -> AsyncGenerator[str]:
    """Yield SSE-formatted strings from the pipeline event bus.

    Subscribes to the runner's event bus FIRST, then emits catch-up
    events for stages that already progressed (solves the race where
    events fire before the SSE client subscribes).  Then streams live
    events as they arrive.  Sends a keepalive comment every
    *heartbeat_seconds* when no events are available.
    """
    # Race condition guard: pipeline may have finished before SSE connects.
    if not runner.is_active(project_id):
        yield _make_sse_payload("complete", project_id)
        return

    # Subscribe FIRST so events emitted after this point are queued.
    queue = runner.event_bus.subscribe(project_id)
    try:
        # Emit catch-up events for stages that already progressed.
        async for frame in _emit_catchup_events(project_id, runner):
            yield frame

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds)
            except TimeoutError:
                yield ": heartbeat\n\n"
                if not runner.is_active(project_id):
                    yield _make_sse_payload("complete", project_id)
                    break
                continue

            payload = PipelineSSEEvent(
                event_type=event.event_type.value,
                project_id=event.project_id,
                stage=event.stage,
                agent=event.agent,
                model=event.model,
                message=event.message,
                detail=dict(event.detail),
                timestamp=event.timestamp.isoformat(),
                elapsed_seconds=event.elapsed_seconds,
                tokens_used=event.tokens_used,
                agent_state=event.detail.get("agent_state", ""),
                target_agent=event.detail.get("target_agent", ""),
            )
            yield f"event: {event.event_type.value}\ndata: {payload.model_dump_json()}\n\n"

            if event.event_type in _TERMINAL_EVENTS:
                break
    finally:
        runner.event_bus.unsubscribe(project_id, queue)


@router.get("/projects/{project_id}/pipeline/events")
async def stream_pipeline_events(
    project_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(require_role(Permission.VIEW_PROJECT))],
    runner: PipelineRunner = Depends(get_pipeline_runner),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> StreamingResponse:
    """SSE endpoint for real-time pipeline progress.

    Consumes events from the in-process event bus instead of polling.
    Sends a keepalive comment every ``sse_heartbeat_seconds``.
    """
    return StreamingResponse(
        _sse_event_generator(str(project_id), runner, settings.sse_heartbeat_seconds),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/projects/{project_id}/pipeline/resume")
async def resume_pipeline(
    project_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    user: Annotated[CurrentUser, Depends(require_role(Permission.APPROVE_DECISION))],
    runner: PipelineRunner = Depends(get_pipeline_runner),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict[str, str]:
    """Resume a paused pipeline (after approval).

    Runs the actual pipeline resumption as a background task so
    the HTTP response returns immediately (the implementation stage
    can take 10+ minutes).  Progress is streamed via SSE/WebSocket.
    """
    pid = str(project_id)
    thread_id: str | None = None

    if not runner.is_active(pid):
        # Fallback: check DB for a paused pipeline (handles server restart).
        run_repo = PipelineRunRepository(db)
        runs = await run_repo.list_for_project(project_id, limit=1)
        if runs and runs[0].status == "awaiting_approval" and runs[0].thread_id:
            runner.rehydrate(pid, runs[0].thread_id)
            thread_id = runs[0].thread_id
        else:
            raise HTTPException(status_code=404, detail="No active pipeline to resume")
    else:
        thread_id = runner.get_thread_id(pid) or ""

    from colette.api.routes.approvals import _resume_pipeline_bg

    background_tasks.add_task(_resume_pipeline_bg, runner, pid, thread_id or "")
    return {"status": "resumed", "project_id": pid}

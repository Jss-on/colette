"""Pipeline status and SSE streaming routes (NFR-USA-003)."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
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


async def _sse_event_generator(
    project_id: str,
    runner: PipelineRunner,
    heartbeat_seconds: float,
) -> AsyncGenerator[str]:
    """Yield SSE-formatted strings from the pipeline event bus.

    Subscribes to the runner's event bus and streams events as they
    arrive.  Sends a keepalive comment every *heartbeat_seconds* when
    no events are available.
    """
    # Race condition guard: pipeline may have finished before SSE connects.
    if not runner.is_active(project_id):
        payload = PipelineSSEEvent(
            event_type="complete",
            project_id=project_id,
            timestamp=datetime.now(UTC).isoformat(),
        )
        yield f"event: complete\ndata: {payload.model_dump_json()}\n\n"
        return

    queue = runner.event_bus.subscribe(project_id)
    try:
        while True:
            try:
                event = await asyncio.wait_for(
                    queue.get(), timeout=heartbeat_seconds
                )
            except TimeoutError:
                yield ": heartbeat\n\n"
                if not runner.is_active(project_id):
                    payload = PipelineSSEEvent(
                        event_type="complete",
                        project_id=project_id,
                        timestamp=datetime.now(UTC).isoformat(),
                    )
                    yield f"event: complete\ndata: {payload.model_dump_json()}\n\n"
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
        _sse_event_generator(
            str(project_id), runner, settings.sse_heartbeat_seconds
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/projects/{project_id}/pipeline/resume")
async def resume_pipeline(
    project_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(require_role(Permission.APPROVE_DECISION))],
    runner: PipelineRunner = Depends(get_pipeline_runner),  # noqa: B008
) -> dict[str, str]:
    """Resume a paused pipeline (after approval)."""
    pid = str(project_id)
    if not runner.is_active(pid):
        raise HTTPException(status_code=404, detail="No active pipeline to resume")
    await runner.resume(pid)
    return {"status": "resumed", "project_id": pid}

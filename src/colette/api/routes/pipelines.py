"""Pipeline status and SSE streaming routes (NFR-USA-003)."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from colette.api.deps import CurrentUser, get_db, get_pipeline_runner, get_settings, require_role
from colette.api.schemas import PipelineStatusResponse
from colette.config import Settings
from colette.db.repositories import PipelineRunRepository
from colette.orchestrator.runner import PipelineRunner
from colette.security.rbac import Permission

router = APIRouter()


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


@router.get("/projects/{project_id}/pipeline/events")
async def stream_pipeline_events(
    project_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(require_role(Permission.VIEW_PROJECT))],
    runner: PipelineRunner = Depends(get_pipeline_runner),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> StreamingResponse:
    """SSE endpoint for real-time pipeline progress."""

    async def event_generator() -> AsyncGenerator[str]:
        pid = str(project_id)
        last_stage = ""
        while True:
            if not runner.is_active(pid):
                yield f"data: {json.dumps({'event': 'complete', 'project_id': pid})}\n\n"
                break
            try:
                progress = await runner.get_progress(pid)
                event_data = {
                    "event": "progress",
                    "project_id": progress.project_id,
                    "stage": progress.stage,
                    "status": progress.status,
                    "elapsed_seconds": progress.elapsed_seconds,
                    "tokens_used": progress.tokens_used,
                    "timestamp": progress.timestamp.isoformat(),
                }
                # Only emit when stage changes or periodically.
                if progress.stage != last_stage:
                    last_stage = progress.stage
                yield f"data: {json.dumps(event_data)}\n\n"
            except KeyError:
                yield f"data: {json.dumps({'event': 'complete', 'project_id': pid})}\n\n"
                break
            await asyncio.sleep(settings.progress_stream_interval_seconds)

    return StreamingResponse(
        event_generator(),
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

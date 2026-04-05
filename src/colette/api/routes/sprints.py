"""Sprint lifecycle API routes (Phase 4)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from colette.schemas.backlog import SprintStatus
from colette.services.backlog_manager import BacklogManager

router = APIRouter()

# Shared manager (same process singleton as backlog routes).
_manager = BacklogManager()


def get_manager() -> BacklogManager:
    """Return the singleton BacklogManager."""
    return _manager


@router.post("/{project_id}/sprints/{sprint_number}/start")
async def start_sprint(project_id: str, sprint_number: int) -> dict[str, Any]:
    """Mark a sprint as active."""
    mgr = get_manager()
    backlog = mgr.get_backlog(project_id)

    sprint = next(
        (s for s in backlog.sprints if s.number == sprint_number),
        None,
    )
    if sprint is None:
        raise HTTPException(status_code=404, detail="Sprint not found")

    if sprint.status != SprintStatus.PLANNING:
        raise HTTPException(
            status_code=400,
            detail=f"Sprint is {sprint.status}, cannot start",
        )

    # Update sprint status in manager storage
    from datetime import UTC, datetime

    updated = sprint.model_copy(
        update={"status": SprintStatus.ACTIVE, "started_at": datetime.now(UTC)}
    )
    mgr._sprints[sprint.id] = updated
    return updated.model_dump()


@router.post("/{project_id}/sprints/{sprint_number}/complete")
async def complete_sprint(project_id: str, sprint_number: int) -> dict[str, Any]:
    """Mark a sprint as complete."""
    mgr = get_manager()
    backlog = mgr.get_backlog(project_id)

    sprint = next(
        (s for s in backlog.sprints if s.number == sprint_number),
        None,
    )
    if sprint is None:
        raise HTTPException(status_code=404, detail="Sprint not found")

    from datetime import UTC, datetime

    updated = sprint.model_copy(
        update={"status": SprintStatus.COMPLETE, "completed_at": datetime.now(UTC)}
    )
    mgr._sprints[sprint.id] = updated
    return updated.model_dump()


@router.get("/{project_id}/sprints/{sprint_number}/status")
async def sprint_status(project_id: str, sprint_number: int) -> dict[str, Any]:
    """Get the current status of a sprint."""
    mgr = get_manager()
    backlog = mgr.get_backlog(project_id)

    sprint = next(
        (s for s in backlog.sprints if s.number == sprint_number),
        None,
    )
    if sprint is None:
        raise HTTPException(status_code=404, detail="Sprint not found")

    return {
        "sprint_id": sprint.id,
        "number": sprint.number,
        "status": sprint.status,
        "goal": sprint.goal,
        "work_items": sprint.work_items,
    }

"""Backlog and sprint API routes (Phase 3)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from colette.schemas.backlog import (
    BacklogPriority,
    ItemSource,
    ItemStatus,
    WorkItemType,
)
from colette.services.backlog_manager import BacklogManager

router = APIRouter()

# Shared in-memory manager (per-process singleton).
_manager = BacklogManager()


def get_manager() -> BacklogManager:
    """Return the singleton BacklogManager."""
    return _manager


# ── Request/Response models ────────────────────────────────────────────


class CreateWorkItemRequest(BaseModel):
    type: WorkItemType
    title: str
    description: str
    priority: BacklogPriority = BacklogPriority.P2_MEDIUM
    acceptance_criteria: list[str] = Field(default_factory=list)
    source: ItemSource = ItemSource.USER
    stage_scope: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)


class CreateSprintRequest(BaseModel):
    goal: str
    work_item_ids: list[str]


# ── Routes ─────────────────────────────────────────────────────────────


@router.post("/{project_id}/backlog")
async def add_work_item(
    project_id: str,
    body: CreateWorkItemRequest,
) -> dict[str, Any]:
    """Add a work item to the project backlog."""
    mgr = get_manager()
    item = mgr.create_work_item(project_id, body.model_dump())
    return item.model_dump()


@router.get("/{project_id}/backlog")
async def get_backlog(project_id: str) -> dict[str, Any]:
    """Get the full backlog for a project."""
    mgr = get_manager()
    backlog = mgr.get_backlog(project_id)
    return backlog.model_dump()


@router.post("/{project_id}/sprints")
async def create_sprint(
    project_id: str,
    body: CreateSprintRequest,
) -> dict[str, Any]:
    """Create a new sprint for the project."""
    mgr = get_manager()
    sprint = mgr.create_sprint(project_id, body.goal, body.work_item_ids)
    return sprint.model_dump()


@router.get("/{project_id}/sprints")
async def list_sprints(project_id: str) -> list[dict[str, Any]]:
    """List all sprints for a project."""
    mgr = get_manager()
    backlog = mgr.get_backlog(project_id)
    return [s.model_dump() for s in backlog.sprints]


@router.get("/{project_id}/sprints/{sprint_id}")
async def get_sprint(project_id: str, sprint_id: str) -> dict[str, Any]:
    """Get a specific sprint."""
    mgr = get_manager()
    sprint = mgr.get_sprint(sprint_id)
    if sprint is None or sprint.project_id != project_id:
        raise HTTPException(status_code=404, detail="Sprint not found")
    return sprint.model_dump()


@router.patch("/{project_id}/backlog/{item_id}/status")
async def update_item_status(
    project_id: str,
    item_id: str,
    status: ItemStatus,
) -> dict[str, Any]:
    """Update the status of a work item."""
    mgr = get_manager()
    try:
        item = mgr.update_item_status(item_id, status)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return item.model_dump()

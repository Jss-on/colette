"""Bug report API routes (Phase 5)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from colette.schemas.backlog import BacklogPriority
from colette.schemas.bug import BugReport
from colette.services.backlog_manager import BacklogManager

router = APIRouter()

_manager = BacklogManager()
_bug_store: dict[str, list[BugReport]] = {}


class CreateBugRequest(BaseModel):
    title: str
    description: str
    reproduction_steps: list[str] = Field(default_factory=list)
    severity: BacklogPriority = BacklogPriority.P2_MEDIUM
    work_item_id: str = ""


@router.post("/{project_id}/bugs")
async def submit_bug(project_id: str, body: CreateBugRequest) -> dict[str, Any]:
    """Submit a bug report."""
    import uuid

    bug_id = f"BUG-{uuid.uuid4().hex[:8]}"
    bug = BugReport(
        id=bug_id,
        title=body.title,
        description=body.description,
        reproduction_steps=body.reproduction_steps,
        severity=body.severity,
        work_item_id=body.work_item_id,
    )
    _bug_store.setdefault(project_id, []).append(bug)
    return bug.model_dump()


@router.get("/{project_id}/bugs")
async def list_bugs(project_id: str) -> list[dict[str, Any]]:
    """List all bugs for a project."""
    bugs = _bug_store.get(project_id, [])
    return [b.model_dump() for b in bugs]


@router.get("/{project_id}/bugs/{bug_id}")
async def get_bug(project_id: str, bug_id: str) -> dict[str, Any]:
    """Get a specific bug report."""
    bugs = _bug_store.get(project_id, [])
    bug = next((b for b in bugs if b.id == bug_id), None)
    if bug is None:
        raise HTTPException(status_code=404, detail="Bug not found")
    return bug.model_dump()

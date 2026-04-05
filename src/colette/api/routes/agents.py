"""Agent presence and conversation REST endpoints for the Web UI."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException

from colette.api.deps import get_pipeline_runner, get_settings
from colette.orchestrator.agent_presence import AgentPresenceTracker

router = APIRouter()

# Module-level tracker shared with the event-bus callbacks.
_tracker = AgentPresenceTracker()


def get_tracker() -> AgentPresenceTracker:
    """Return the module-level presence tracker (test seam)."""
    return _tracker


def _presence_to_dict(p: object) -> dict[str, Any]:
    from colette.orchestrator.agent_presence import AgentPresence

    if not isinstance(p, AgentPresence):
        return {}
    return {
        "agent_id": p.agent_id,
        "display_name": p.display_name,
        "stage": p.stage,
        "state": p.state.value,
        "activity": p.activity,
        "model": p.model,
        "tokens_used": p.tokens_used,
        "target_agent": p.target_agent,
        "started_at": p.started_at.isoformat(),
    }


def _conversation_to_dict(e: object) -> dict[str, Any]:
    from colette.orchestrator.agent_presence import ConversationEntry

    if not isinstance(e, ConversationEntry):
        return {}
    ts = e.timestamp
    if not hasattr(ts, "isoformat"):
        ts = datetime.now(UTC)
    return {
        "agent_id": e.agent_id,
        "display_name": e.display_name,
        "stage": e.stage,
        "message": e.message,
        "timestamp": ts.isoformat(),
        "target_agent": e.target_agent,
    }


@router.get("/{project_id}/agents")
async def get_agents(project_id: str) -> dict[str, Any]:
    """Return all agent presence records for a project."""
    settings = get_settings()
    runner = get_pipeline_runner(settings)
    if not runner.is_active(project_id):
        # Check if project exists at all
        try:
            await runner.get_progress(project_id)
        except Exception:
            raise HTTPException(status_code=404, detail="Project not found") from None
    tracker = get_tracker()
    agents = tracker.get_agents(project_id)
    return {"agents": [_presence_to_dict(a) for a in agents]}


@router.get("/{project_id}/conversation")
async def get_conversation(project_id: str) -> dict[str, Any]:
    """Return the conversation ring buffer for a project."""
    settings = get_settings()
    runner = get_pipeline_runner(settings)
    if not runner.is_active(project_id):
        try:
            await runner.get_progress(project_id)
        except Exception:
            raise HTTPException(status_code=404, detail="Project not found") from None
    tracker = get_tracker()
    entries = tracker.get_conversation(project_id)
    return {"entries": [_conversation_to_dict(e) for e in entries]}

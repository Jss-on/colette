"""Progress streaming for pipeline execution (FR-ORC-007)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class ProgressEvent:
    """A single progress snapshot extracted from pipeline state."""

    project_id: str
    stage: str
    status: str
    gate_result: dict[str, Any] | None
    elapsed_seconds: float
    tokens_used: int
    timestamp: datetime


def state_to_progress_event(state: dict[str, Any]) -> ProgressEvent:
    """Extract a ``ProgressEvent`` from the current pipeline state."""
    started = state.get("started_at", "")
    now = datetime.now(UTC)
    elapsed = 0.0
    if started:
        try:
            start_dt = datetime.fromisoformat(started)
            elapsed = (now - start_dt).total_seconds()
        except (ValueError, TypeError):
            pass

    current = state.get("current_stage", "unknown")
    gate_results = state.get("quality_gate_results", {})
    latest_gate = gate_results.get(current)

    return ProgressEvent(
        project_id=state.get("project_id", ""),
        stage=current,
        status=state.get("stage_statuses", {}).get(current, "unknown"),
        gate_result=latest_gate,
        elapsed_seconds=round(elapsed, 2),
        tokens_used=state.get("total_tokens_used", 0),
        timestamp=now,
    )

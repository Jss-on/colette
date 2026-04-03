"""Pipeline state definition for LangGraph orchestration (FR-ORC-001)."""

from __future__ import annotations

import operator
from datetime import UTC, datetime
from typing import Annotated, Any

from typing_extensions import TypedDict

from colette.schemas.common import StageName, StageStatus

# Stages in pipeline execution order.
STAGE_ORDER: list[str] = [s.value for s in StageName]


class PipelineState(TypedDict, total=False):
    """Shared state threaded through the LangGraph pipeline.

    Fields annotated with ``operator.add`` are append-only reducers so
    concurrent nodes (e.g. parallel specialists via ``Send``) can each
    append without overwriting each other.
    """

    # ── Identity ─────────────────────────────────────────────────────
    project_id: str
    pipeline_run_id: str

    # ── Stage tracking ───────────────────────────────────────────────
    current_stage: str
    stage_statuses: dict[str, str]

    # ── Handoff payloads (serialised dicts keyed by stage name) ──────
    handoffs: dict[str, dict[str, Any]]

    # ── Quality gate results (keyed by gate name) ────────────────────
    quality_gate_results: dict[str, dict[str, Any]]

    # ── Human-in-the-loop ────────────────────────────────────────────
    approval_requests: Annotated[list[dict[str, Any]], operator.add]
    approval_decisions: Annotated[list[dict[str, Any]], operator.add]

    # ── Observability (append-only) ──────────────────────────────────
    progress_events: Annotated[list[dict[str, Any]], operator.add]
    error_log: Annotated[list[dict[str, Any]], operator.add]

    # ── Configuration ────────────────────────────────────────────────
    skip_stages: list[str]

    # ── Timing & cost ────────────────────────────────────────────────
    started_at: str
    completed_at: str | None
    total_tokens_used: int

    # ── User input ───────────────────────────────────────────────────
    user_request: str

    # ── Rework loops (Phase 1) ──────────────────────────────────────
    rework_count: dict[str, int]
    rework_directives: Annotated[list[dict[str, Any]], operator.add]
    current_rework: dict[str, Any] | None

    # ── Backlog & sprints (Phase 3) ────────────────────────────────
    backlog: dict[str, Any] | None
    current_sprint: dict[str, Any] | None
    work_items: list[dict[str, Any]]

    # ── Extensible bag ───────────────────────────────────────────────
    metadata: dict[str, Any]


def create_initial_state(
    project_id: str,
    *,
    pipeline_run_id: str = "",
    user_request: str = "",
) -> PipelineState:
    """Build a fresh ``PipelineState`` with all fields initialised."""
    now = datetime.now(UTC).isoformat()
    return PipelineState(
        project_id=project_id,
        pipeline_run_id=pipeline_run_id or f"{project_id}-{now}",
        current_stage=StageName.REQUIREMENTS.value,
        stage_statuses=dict.fromkeys(STAGE_ORDER, StageStatus.PENDING.value),
        handoffs={},
        quality_gate_results={},
        approval_requests=[],
        approval_decisions=[],
        progress_events=[],
        error_log=[],
        skip_stages=[],
        user_request=user_request,
        started_at=now,
        completed_at=None,
        total_tokens_used=0,
        rework_count={},
        rework_directives=[],
        current_rework=None,
        backlog=None,
        current_sprint=None,
        work_items=[],
        metadata={},
    )

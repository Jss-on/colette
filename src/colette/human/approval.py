"""Approval routing and interrupt/resume wiring (FR-HIL-001/008)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from colette.config import Settings
from colette.human.models import ApprovalRequest
from colette.human.sla import compute_deadline
from colette.orchestrator.event_bus import (
    EventType,
    PipelineEvent,
    event_bus_var,
    project_id_var,
    stage_var,
)
from colette.schemas.common import ApprovalTier


def determine_approval_action(
    tier: ApprovalTier,
    confidence: float | None,
    settings: Settings,
) -> str:
    """Decide whether to interrupt for human review or auto-approve.

    Returns
    -------
    str
        ``"interrupt"`` — pause pipeline for human review.
        ``"auto_approve"`` — proceed without human review.
    """
    if tier in (ApprovalTier.T0_CRITICAL, ApprovalTier.T1_HIGH):
        return "interrupt"
    if tier == ApprovalTier.T2_MODERATE:
        if confidence is None or confidence < settings.hil_confidence_flag_threshold:
            return "interrupt"
        return "auto_approve"
    # T3_ROUTINE — always auto-approve
    return "auto_approve"


def create_approval_request(
    state: dict[str, Any],
    tier: ApprovalTier,
    context_summary: str,
    proposed_action: str,
    *,
    confidence: float | None = None,
    risk_assessment: str = "",
    settings: Settings | None = None,
) -> ApprovalRequest:
    """Build a complete ``ApprovalRequest`` from pipeline state."""
    now = datetime.now(UTC)
    _settings = settings or Settings()
    deadline = compute_deadline(tier, now, _settings)

    return ApprovalRequest(
        request_id=str(uuid.uuid4()),
        project_id=state.get("project_id", ""),
        stage=state.get("current_stage", ""),
        tier=tier,
        context_summary=context_summary,
        proposed_action=proposed_action,
        risk_assessment=risk_assessment,
        confidence_score=confidence,
        sla_deadline=deadline if deadline.year < 9999 else None,
        created_at=now,
    )


def apply_modifications(
    handoff_dict: dict[str, Any],
    modifications: dict[str, object],
) -> dict[str, Any]:
    """Merge inline modifications into a handoff dict (FR-HIL-008).

    Returns a new dict — the original is not mutated.
    Emits a ``FEEDBACK_APPLIED`` event when modifications are non-empty.
    """
    if not modifications:
        return handoff_dict

    result = {**handoff_dict, **modifications}

    bus = event_bus_var.get()
    if bus is not None:
        bus.emit(
            PipelineEvent(
                project_id=project_id_var.get(""),
                event_type=EventType.FEEDBACK_APPLIED,
                stage=stage_var.get(""),
                message=f"Applied {len(modifications)} modification(s) to handoff.",
                detail={"keys": list(modifications.keys())},
            )
        )

    return result

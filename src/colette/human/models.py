"""HIL data models — approval requests, decisions, and confidence (FR-HIL-001/003)."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from colette.schemas.common import ApprovalStatus, ApprovalTier


class ApprovalRequest(BaseModel, frozen=True):
    """A structured review package sent to a human reviewer (FR-HIL-003)."""

    request_id: str
    project_id: str
    stage: str
    tier: ApprovalTier
    context_summary: str = Field(description="2-3 sentence summary of what happened.")
    proposed_action: str = Field(description="Exact change being proposed.")
    risk_assessment: str = ""
    alternatives: list[str] = Field(default_factory=list)
    confidence_score: float | None = None
    sla_deadline: datetime | None = None
    review_url: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ApprovalDecision(BaseModel, frozen=True):
    """A reviewer's decision on an approval request (FR-HIL-008)."""

    request_id: str
    reviewer_id: str
    status: ApprovalStatus
    stage: str = ""
    modifications: dict[str, object] = Field(default_factory=dict)
    comments: str = ""
    decided_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ConfidenceResult(BaseModel, frozen=True):
    """Result of confidence evaluation with recommended action (FR-HIL-002)."""

    score: float = Field(ge=0.0, le=1.0)
    action: str = Field(description="auto_approve | flag_for_review | escalate")
    reasoning: str = ""

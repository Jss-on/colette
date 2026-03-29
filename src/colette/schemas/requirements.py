"""Requirements → Design handoff schema (FR-ORC-020, §4)."""

from __future__ import annotations

from pydantic import Field

from colette.schemas.base import HandoffSchema
from colette.schemas.common import (
    ApprovalRecord,
    NFRSpec,
    TechConstraint,
    UserStory,
)


class RequirementsToDesignHandoff(HandoffSchema):
    """Structured output of the Requirements stage consumed by Design."""

    source_stage: str = "requirements"
    target_stage: str = "design"
    schema_version: str = "1.0.0"

    # ── PRD content (FR-REQ-003) ─────────────────────────────────────
    project_overview: str = Field(description="Executive summary of the project.")
    functional_requirements: list[UserStory] = Field(
        min_length=1,
        description="User stories with acceptance criteria.",
    )
    nonfunctional_requirements: list[NFRSpec] = Field(default_factory=list)
    tech_constraints: list[TechConstraint] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)

    # ── Quality (FR-REQ-006) ─────────────────────────────────────────
    completeness_score: float = Field(ge=0.0, le=1.0)
    open_questions: list[str] = Field(default_factory=list)

    # ── Approval (FR-HIL-001) ────────────────────────────────────────
    approval: ApprovalRecord | None = None

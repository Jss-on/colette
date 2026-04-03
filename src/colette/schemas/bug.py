"""Bug report schema for targeted rework flows (Phase 5)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from colette.schemas.backlog import BacklogPriority


class BugReport(BaseModel):
    """A bug report that triggers scoped pipeline re-runs."""

    model_config = ConfigDict(frozen=True)

    id: str
    work_item_id: str = Field(default="", description="Linked work item ID.")
    title: str
    description: str
    reproduction_steps: list[str] = Field(default_factory=list)
    severity: BacklogPriority = BacklogPriority.P2_MEDIUM
    affected_stage: str | None = Field(
        default=None,
        description="Set by triage: requirements | design | implementation | testing",
    )
    root_cause_analysis: str | None = None
    regression_test_needed: bool = True

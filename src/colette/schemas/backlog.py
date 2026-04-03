"""Backlog and sprint schemas for structured work management (Phase 3)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class WorkItemType(StrEnum):
    FEATURE = "feature"
    BUG = "bug"
    IMPROVEMENT = "improvement"
    TECH_DEBT = "tech_debt"
    SPIKE = "spike"


class BacklogPriority(StrEnum):
    P0_CRITICAL = "p0_critical"
    P1_HIGH = "p1_high"
    P2_MEDIUM = "p2_medium"
    P3_LOW = "p3_low"


class ItemStatus(StrEnum):
    BACKLOG = "backlog"
    SPRINT = "sprint"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


class ItemSource(StrEnum):
    USER = "user"
    GATE_FEEDBACK = "gate_feedback"
    TEST_FAILURE = "test_failure"
    RETROSPECTIVE = "retrospective"
    BUG_REPORT = "bug_report"


class WorkItem(BaseModel):
    """A single backlog work item."""

    model_config = ConfigDict(frozen=True)

    id: str
    type: WorkItemType
    title: str
    description: str
    priority: BacklogPriority
    status: ItemStatus = ItemStatus.BACKLOG
    sprint_id: str | None = None
    parent_id: str | None = None
    acceptance_criteria: list[str] = Field(default_factory=list)
    source: ItemSource = ItemSource.USER
    stage_scope: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)


class SprintStatus(StrEnum):
    PLANNING = "planning"
    ACTIVE = "active"
    REVIEW = "review"
    COMPLETE = "complete"


class Sprint(BaseModel):
    """A sprint containing a subset of backlog work items."""

    model_config = ConfigDict(frozen=True)

    id: str
    project_id: str
    number: int
    goal: str
    work_items: list[str] = Field(default_factory=list)
    status: SprintStatus = SprintStatus.PLANNING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    retrospective: dict[str, object] | None = None


class Backlog(BaseModel):
    """Full project backlog with items and sprints."""

    model_config = ConfigDict(frozen=True)

    project_id: str
    items: list[WorkItem] = Field(default_factory=list)
    sprints: list[Sprint] = Field(default_factory=list)

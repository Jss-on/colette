"""Tests for backlog schemas (Phase 3)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from colette.schemas.backlog import (
    Backlog,
    BacklogPriority,
    ItemSource,
    ItemStatus,
    Sprint,
    SprintStatus,
    WorkItem,
    WorkItemType,
)


class TestWorkItemType:
    def test_values(self) -> None:
        assert WorkItemType.FEATURE == "feature"
        assert WorkItemType.BUG == "bug"
        assert WorkItemType.TECH_DEBT == "tech_debt"


class TestBacklogPriority:
    def test_ordering(self) -> None:
        assert BacklogPriority.P0_CRITICAL == "p0_critical"
        assert BacklogPriority.P3_LOW == "p3_low"


class TestWorkItem:
    def test_minimal(self) -> None:
        item = WorkItem(
            id="WI-001",
            type=WorkItemType.FEATURE,
            title="Add login",
            description="Implement login page",
            priority=BacklogPriority.P1_HIGH,
        )
        assert item.id == "WI-001"
        assert item.status == ItemStatus.BACKLOG
        assert item.source == ItemSource.USER
        assert item.acceptance_criteria == []

    def test_full(self) -> None:
        item = WorkItem(
            id="WI-002",
            type=WorkItemType.BUG,
            title="Fix crash",
            description="App crashes on empty input",
            priority=BacklogPriority.P0_CRITICAL,
            status=ItemStatus.IN_PROGRESS,
            sprint_id="SPRINT-1",
            parent_id="WI-001",
            acceptance_criteria=["No crash on empty input"],
            source=ItemSource.BUG_REPORT,
            stage_scope=["implementation", "testing"],
            depends_on=["WI-001"],
        )
        assert item.sprint_id == "SPRINT-1"
        assert len(item.acceptance_criteria) == 1
        assert item.depends_on == ["WI-001"]

    def test_frozen(self) -> None:
        item = WorkItem(
            id="WI-001",
            type=WorkItemType.FEATURE,
            title="t",
            description="d",
            priority=BacklogPriority.P2_MEDIUM,
        )
        with pytest.raises(ValidationError):
            item.title = "new"  # type: ignore[misc]

    def test_serialization_roundtrip(self) -> None:
        item = WorkItem(
            id="WI-003",
            type=WorkItemType.IMPROVEMENT,
            title="Improve perf",
            description="Optimize queries",
            priority=BacklogPriority.P2_MEDIUM,
        )
        data = item.model_dump()
        restored = WorkItem.model_validate(data)
        assert restored == item


class TestSprint:
    def test_minimal(self) -> None:
        sprint = Sprint(
            id="S-1",
            project_id="proj-1",
            number=1,
            goal="MVP",
        )
        assert sprint.status == SprintStatus.PLANNING
        assert sprint.work_items == []
        assert sprint.started_at is None

    def test_frozen(self) -> None:
        sprint = Sprint(id="S-1", project_id="p", number=1, goal="g")
        with pytest.raises(ValidationError):
            sprint.goal = "new"  # type: ignore[misc]


class TestBacklog:
    def test_empty(self) -> None:
        backlog = Backlog(project_id="proj-1")
        assert backlog.items == []
        assert backlog.sprints == []

    def test_with_items(self) -> None:
        item = WorkItem(
            id="WI-001",
            type=WorkItemType.FEATURE,
            title="t",
            description="d",
            priority=BacklogPriority.P1_HIGH,
        )
        backlog = Backlog(project_id="proj-1", items=[item])
        assert len(backlog.items) == 1

    def test_frozen(self) -> None:
        backlog = Backlog(project_id="proj-1")
        with pytest.raises(ValidationError):
            backlog.project_id = "new"  # type: ignore[misc]

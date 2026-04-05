"""Tests for BacklogManager (Phase 3)."""

from __future__ import annotations

import pytest

from colette.schemas.backlog import (
    BacklogPriority,
    ItemSource,
    ItemStatus,
    SprintStatus,
    WorkItemType,
)
from colette.services.backlog_manager import BacklogManager


def _item_data(**overrides: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "type": WorkItemType.FEATURE,
        "title": "Add login",
        "description": "Implement login page",
        "priority": BacklogPriority.P1_HIGH,
        "acceptance_criteria": ["Login works"],
        "source": ItemSource.USER,
        "stage_scope": ["implementation"],
    }
    defaults.update(overrides)
    return defaults


class TestCreateWorkItem:
    def test_creates_item(self) -> None:
        mgr = BacklogManager()
        item = mgr.create_work_item("proj-1", _item_data())
        assert item.title == "Add login"
        assert item.status == ItemStatus.BACKLOG

    def test_assigns_id(self) -> None:
        mgr = BacklogManager()
        item = mgr.create_work_item("proj-1", _item_data())
        assert item.id.startswith("WI-")

    def test_custom_id(self) -> None:
        mgr = BacklogManager()
        item = mgr.create_work_item("proj-1", _item_data(id="MY-001"))
        assert item.id == "MY-001"

    def test_appears_in_backlog(self) -> None:
        mgr = BacklogManager()
        mgr.create_work_item("proj-1", _item_data())
        backlog = mgr.get_backlog("proj-1")
        assert len(backlog.items) == 1


class TestGetBacklog:
    def test_empty_project(self) -> None:
        mgr = BacklogManager()
        backlog = mgr.get_backlog("nonexistent")
        assert backlog.project_id == "nonexistent"
        assert backlog.items == []
        assert backlog.sprints == []

    def test_multiple_items(self) -> None:
        mgr = BacklogManager()
        mgr.create_work_item("proj-1", _item_data(title="A"))
        mgr.create_work_item("proj-1", _item_data(title="B"))
        backlog = mgr.get_backlog("proj-1")
        assert len(backlog.items) == 2


class TestUpdateItemStatus:
    def test_updates_status(self) -> None:
        mgr = BacklogManager()
        item = mgr.create_work_item("proj-1", _item_data())
        updated = mgr.update_item_status(item.id, ItemStatus.IN_PROGRESS)
        assert updated.status == ItemStatus.IN_PROGRESS
        assert updated.title == item.title

    def test_nonexistent_raises(self) -> None:
        mgr = BacklogManager()
        with pytest.raises(KeyError):
            mgr.update_item_status("FAKE", ItemStatus.DONE)


class TestPrioritize:
    def test_sorts_by_priority(self) -> None:
        mgr = BacklogManager()
        mgr.create_work_item("proj-1", _item_data(id="low", priority=BacklogPriority.P3_LOW))
        mgr.create_work_item("proj-1", _item_data(id="crit", priority=BacklogPriority.P0_CRITICAL))
        mgr.create_work_item("proj-1", _item_data(id="med", priority=BacklogPriority.P2_MEDIUM))

        sorted_items = mgr.prioritize("proj-1")
        assert sorted_items[0].id == "crit"
        assert sorted_items[1].id == "med"
        assert sorted_items[2].id == "low"


class TestCreateSprint:
    def test_creates_sprint(self) -> None:
        mgr = BacklogManager()
        item = mgr.create_work_item("proj-1", _item_data())
        sprint = mgr.create_sprint("proj-1", "MVP launch", [item.id])
        assert sprint.goal == "MVP launch"
        assert sprint.number == 1
        assert sprint.status == SprintStatus.PLANNING
        assert item.id in sprint.work_items

    def test_items_marked_sprint(self) -> None:
        mgr = BacklogManager()
        item = mgr.create_work_item("proj-1", _item_data())
        sprint = mgr.create_sprint("proj-1", "MVP", [item.id])
        updated = mgr.get_work_item(item.id)
        assert updated is not None
        assert updated.status == ItemStatus.SPRINT
        assert updated.sprint_id == sprint.id

    def test_sprint_numbering(self) -> None:
        mgr = BacklogManager()
        s1 = mgr.create_sprint("proj-1", "Sprint 1", [])
        s2 = mgr.create_sprint("proj-1", "Sprint 2", [])
        assert s1.number == 1
        assert s2.number == 2

    def test_appears_in_backlog(self) -> None:
        mgr = BacklogManager()
        mgr.create_sprint("proj-1", "MVP", [])
        backlog = mgr.get_backlog("proj-1")
        assert len(backlog.sprints) == 1


class TestGetSprint:
    def test_existing(self) -> None:
        mgr = BacklogManager()
        sprint = mgr.create_sprint("proj-1", "MVP", [])
        result = mgr.get_sprint(sprint.id)
        assert result is not None
        assert result.goal == "MVP"

    def test_nonexistent(self) -> None:
        mgr = BacklogManager()
        assert mgr.get_sprint("FAKE") is None

"""Tests for SprintRunner (Phase 4)."""

from __future__ import annotations

import pytest

from colette.orchestrator.sprint_runner import SprintRunner
from colette.schemas.backlog import (
    BacklogPriority,
    ItemSource,
    ItemStatus,
    SprintStatus,
    WorkItemType,
)
from colette.schemas.evolution import RequirementAmendment
from colette.services.backlog_manager import BacklogManager


def _create_items(mgr: BacklogManager, project_id: str, count: int = 2) -> list[str]:
    ids = []
    for i in range(count):
        item = mgr.create_work_item(
            project_id,
            {
                "id": f"WI-{i + 1:03d}",
                "type": WorkItemType.FEATURE,
                "title": f"Item {i + 1}",
                "description": f"Description {i + 1}",
                "priority": BacklogPriority.P1_HIGH,
                "source": ItemSource.USER,
            },
        )
        ids.append(item.id)
    return ids


class TestSprintRunner:
    @pytest.mark.asyncio
    async def test_start_sprint(self) -> None:
        mgr = BacklogManager()
        runner = SprintRunner(mgr)
        ids = _create_items(mgr, "proj-1")
        sprint = mgr.create_sprint("proj-1", "MVP", ids)

        result = await runner.start_sprint("proj-1", sprint)
        assert result.sprint_number == 1
        assert result.status == SprintStatus.COMPLETE
        assert result.completed_items == ids

    @pytest.mark.asyncio
    async def test_items_marked_done(self) -> None:
        mgr = BacklogManager()
        runner = SprintRunner(mgr)
        ids = _create_items(mgr, "proj-1")
        sprint = mgr.create_sprint("proj-1", "MVP", ids)

        await runner.start_sprint("proj-1", sprint)
        for iid in ids:
            item = mgr.get_work_item(iid)
            assert item is not None
            assert item.status == ItemStatus.DONE

    @pytest.mark.asyncio
    async def test_sprint_history(self) -> None:
        mgr = BacklogManager()
        runner = SprintRunner(mgr)
        sprint = mgr.create_sprint("proj-1", "Sprint 1", [])

        await runner.start_sprint("proj-1", sprint)
        history = runner.get_sprint_history("proj-1")
        assert len(history) == 1
        assert history[0].sprint_id == sprint.id

    def test_empty_history(self) -> None:
        mgr = BacklogManager()
        runner = SprintRunner(mgr)
        assert runner.get_sprint_history("proj-1") == []

    def test_build_sprint_context_empty(self) -> None:
        mgr = BacklogManager()
        runner = SprintRunner(mgr)
        assert runner.build_sprint_context("proj-1") == {}

    @pytest.mark.asyncio
    async def test_build_sprint_context_after_sprint(self) -> None:
        mgr = BacklogManager()
        runner = SprintRunner(mgr)
        sprint = mgr.create_sprint("proj-1", "Sprint 1", [])

        await runner.start_sprint("proj-1", sprint)
        ctx = runner.build_sprint_context("proj-1")
        assert ctx["prior_sprint_number"] == 1
        assert ctx["total_sprints_completed"] == 1

    def test_amend_requirements(self) -> None:
        mgr = BacklogManager()
        runner = SprintRunner(mgr)
        amendment = RequirementAmendment(
            sprint_id="S-1",
            source="gate_feedback",
            rationale="Added auth requirements",
        )
        result = runner.amend_requirements("proj-1", amendment)
        assert len(result.amendments) == 1

    def test_amend_requirements_accumulates(self) -> None:
        mgr = BacklogManager()
        runner = SprintRunner(mgr)

        a1 = RequirementAmendment(sprint_id="S-1", source="gate_feedback")
        a2 = RequirementAmendment(sprint_id="S-2", source="human_review")

        runner.amend_requirements("proj-1", a1)
        result = runner.amend_requirements("proj-1", a2)
        assert len(result.amendments) == 2

    def test_get_evolving_requirements_none(self) -> None:
        mgr = BacklogManager()
        runner = SprintRunner(mgr)
        assert runner.get_evolving_requirements("proj-1") is None

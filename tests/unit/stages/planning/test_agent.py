"""Tests for the planning agent (Phase 3)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from colette.schemas.backlog import BacklogPriority, WorkItem, WorkItemType
from colette.stages.planning.agent import PlanningResult, run_planning_agent


def _sample_result() -> PlanningResult:
    return PlanningResult(
        work_items=[
            WorkItem(
                id="WI-001",
                type=WorkItemType.FEATURE,
                title="User auth",
                description="Implement login/register",
                priority=BacklogPriority.P1_HIGH,
                acceptance_criteria=["Login works"],
                stage_scope=["design", "implementation"],
            ),
            WorkItem(
                id="WI-002",
                type=WorkItemType.FEATURE,
                title="Todo CRUD",
                description="Basic todo operations",
                priority=BacklogPriority.P1_HIGH,
                depends_on=["WI-001"],
            ),
        ],
        project_summary="Todo app with auth",
        estimated_sprints=2,
    )


@pytest.mark.asyncio
async def test_run_planning_agent_basic(settings: object) -> None:
    result = _sample_result()
    with patch(
        "colette.stages.planning.agent.invoke_structured",
        new_callable=AsyncMock,
        return_value=result,
    ) as mock_invoke:
        out = await run_planning_agent("Build a todo app", settings=settings)
        assert len(out.work_items) == 2
        assert out.project_summary == "Todo app with auth"
        assert out.estimated_sprints == 2
        mock_invoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_planning_agent_uses_planning_tier(settings: object) -> None:
    with patch(
        "colette.stages.planning.agent.invoke_structured",
        new_callable=AsyncMock,
        return_value=_sample_result(),
    ) as mock_invoke:
        await run_planning_agent("Build an app", settings=settings)
        call_kwargs = mock_invoke.call_args.kwargs
        assert call_kwargs["model_tier"].value == "planning"


@pytest.mark.asyncio
async def test_planning_result_has_work_items(settings: object) -> None:
    result = _sample_result()
    with patch(
        "colette.stages.planning.agent.invoke_structured",
        new_callable=AsyncMock,
        return_value=result,
    ):
        out = await run_planning_agent("Build a todo app", settings=settings)
        assert out.work_items[0].title == "User auth"
        assert out.work_items[1].depends_on == ["WI-001"]

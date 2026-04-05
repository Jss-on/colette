"""Tests for the sprint planning agent (Phase 4)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from colette.schemas.backlog import BacklogPriority, WorkItem, WorkItemType
from colette.stages.planning.sprint_planning_agent import (
    SprintPlanningResult,
    run_sprint_planning,
)


def _items() -> list[WorkItem]:
    return [
        WorkItem(
            id="WI-001",
            type=WorkItemType.FEATURE,
            title="Auth",
            description="Login",
            priority=BacklogPriority.P0_CRITICAL,
        ),
        WorkItem(
            id="WI-002",
            type=WorkItemType.FEATURE,
            title="CRUD",
            description="Todo CRUD",
            priority=BacklogPriority.P1_HIGH,
            depends_on=["WI-001"],
        ),
    ]


def _result() -> SprintPlanningResult:
    return SprintPlanningResult(
        selected_item_ids=["WI-001"],
        sprint_goal="Implement authentication",
        rationale="Auth is P0 and blocks CRUD",
    )


@pytest.mark.asyncio
async def test_run_sprint_planning(settings: object) -> None:
    with patch(
        "colette.stages.planning.sprint_planning_agent.invoke_structured",
        new_callable=AsyncMock,
        return_value=_result(),
    ) as mock_invoke:
        out = await run_sprint_planning(_items(), settings=settings)
        assert out.selected_item_ids == ["WI-001"]
        assert out.sprint_goal == "Implement authentication"
        mock_invoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_sprint_planning_with_context(settings: object) -> None:
    with patch(
        "colette.stages.planning.sprint_planning_agent.invoke_structured",
        new_callable=AsyncMock,
        return_value=_result(),
    ) as mock_invoke:
        await run_sprint_planning(
            _items(),
            settings=settings,
            prior_sprint_context="Sprint 1 completed auth",
        )
        user_content = mock_invoke.call_args.kwargs["user_content"]
        assert "Prior Sprint Context" in user_content


@pytest.mark.asyncio
async def test_sprint_planning_uses_planning_tier(settings: object) -> None:
    with patch(
        "colette.stages.planning.sprint_planning_agent.invoke_structured",
        new_callable=AsyncMock,
        return_value=_result(),
    ) as mock_invoke:
        await run_sprint_planning(_items(), settings=settings)
        assert mock_invoke.call_args.kwargs["model_tier"].value == "planning"

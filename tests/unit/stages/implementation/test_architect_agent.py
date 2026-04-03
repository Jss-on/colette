"""Tests for the architect agent (Phase 2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from colette.schemas.module_design import (
    InterfaceContract,
    ModuleDesign,
    ModuleSpec,
    TestStrategy,
)
from colette.stages.implementation.architect_agent import run_architect


def _sample_design() -> ModuleDesign:
    return ModuleDesign(
        work_item_id="WI-001",
        module_structure=[
            ModuleSpec(file_path="src/api.py", responsibility="API routes"),
        ],
        interfaces=[
            InterfaceContract(name="get_users", output_type="list[User]"),
        ],
        design_decisions=["REST API"],
        complexity_estimate="M",
        test_strategy=TestStrategy(unit_test_targets=["get_users"]),
    )


@pytest.mark.asyncio
async def test_run_architect_basic(settings: object) -> None:
    design = _sample_design()
    with patch(
        "colette.stages.implementation.architect_agent.invoke_structured",
        new_callable=AsyncMock,
        return_value=design,
    ) as mock_invoke:
        result = await run_architect("design spec", settings=settings)
        assert result.work_item_id == "WI-001"
        assert len(result.module_structure) == 1
        mock_invoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_architect_with_prior_design(settings: object) -> None:
    prior = _sample_design()
    refined = ModuleDesign(
        work_item_id="WI-001",
        module_structure=[
            ModuleSpec(file_path="src/api.py", responsibility="API routes"),
            ModuleSpec(file_path="src/auth.py", responsibility="Auth module"),
        ],
        complexity_estimate="L",
    )
    with patch(
        "colette.stages.implementation.architect_agent.invoke_structured",
        new_callable=AsyncMock,
        return_value=refined,
    ) as mock_invoke:
        result = await run_architect("design spec", settings=settings, prior_design=prior)
        assert len(result.module_structure) == 2
        # Verify the user content includes prior design context
        call_kwargs = mock_invoke.call_args
        assert "Prior Module Design" in call_kwargs.kwargs["user_content"]


@pytest.mark.asyncio
async def test_run_architect_uses_planning_tier(settings: object) -> None:
    with patch(
        "colette.stages.implementation.architect_agent.invoke_structured",
        new_callable=AsyncMock,
        return_value=_sample_design(),
    ) as mock_invoke:
        await run_architect("spec", settings=settings)
        call_kwargs = mock_invoke.call_args.kwargs
        assert call_kwargs["model_tier"].value == "planning"

"""Tests for the test agent — TDD RED phase (Phase 2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from colette.schemas.common import GeneratedFile
from colette.schemas.module_design import (
    InterfaceContract,
    ModuleDesign,
    ModuleSpec,
    TestStrategy,
)
from colette.stages.implementation.test_agent import (
    TestGenerationResult,
    run_test_agent,
)


def _sample_design() -> ModuleDesign:
    return ModuleDesign(
        work_item_id="WI-001",
        module_structure=[
            ModuleSpec(
                file_path="src/users.py",
                responsibility="User CRUD",
                public_api=["create_user", "get_user"],
            ),
        ],
        interfaces=[
            InterfaceContract(
                name="create_user",
                input_types={"name": "str"},
                output_type="User",
                preconditions=["name is non-empty"],
            ),
        ],
        test_strategy=TestStrategy(
            unit_test_targets=["create_user", "get_user"],
            edge_cases=["empty name"],
        ),
    )


def _sample_result() -> TestGenerationResult:
    return TestGenerationResult(
        test_files=[
            GeneratedFile(
                path="tests/test_users.py",
                content="def test_create_user(): pass",
                language="python",
            ),
        ],
        coverage_targets=["create_user"],
    )


@pytest.mark.asyncio
async def test_run_test_agent_basic(settings: object) -> None:
    result = _sample_result()
    with patch(
        "colette.stages.implementation.test_agent.invoke_structured",
        new_callable=AsyncMock,
        return_value=result,
    ) as mock_invoke:
        out = await run_test_agent(_sample_design(), ["users can be created"], settings=settings)
        assert len(out.test_files) == 1
        assert out.test_files[0].path == "tests/test_users.py"
        mock_invoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_test_agent_with_regression(settings: object) -> None:
    result = _sample_result()
    with patch(
        "colette.stages.implementation.test_agent.invoke_structured",
        new_callable=AsyncMock,
        return_value=result,
    ) as mock_invoke:
        await run_test_agent(
            _sample_design(),
            [],
            settings=settings,
            regression_context="Prior failure: missing validation",
        )
        call_kwargs = mock_invoke.call_args.kwargs
        assert "Regression Context" in call_kwargs["user_content"]
        assert "missing validation" in call_kwargs["user_content"]


@pytest.mark.asyncio
async def test_run_test_agent_includes_acceptance_criteria(settings: object) -> None:
    result = _sample_result()
    with patch(
        "colette.stages.implementation.test_agent.invoke_structured",
        new_callable=AsyncMock,
        return_value=result,
    ) as mock_invoke:
        await run_test_agent(
            _sample_design(),
            ["Must handle empty input", "Must return 201"],
            settings=settings,
        )
        call_kwargs = mock_invoke.call_args.kwargs
        assert "Must handle empty input" in call_kwargs["user_content"]
        assert "Must return 201" in call_kwargs["user_content"]

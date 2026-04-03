"""Tests for the retrospective agent (Phase 6)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from colette.schemas.retrospective import SprintRetrospective
from colette.stages.retrospective.agent import run_retrospective


def _retro() -> SprintRetrospective:
    return SprintRetrospective(
        sprint_id="S-1",
        total_rework_cycles=2,
        rework_by_stage={"implementation": 2},
        improvements=["Improve design clarity"],
        config_adjustments={"impl_threshold": 0.70},
    )


@pytest.mark.asyncio
async def test_run_retrospective_basic(settings: object) -> None:
    with patch(
        "colette.stages.retrospective.agent.invoke_structured",
        new_callable=AsyncMock,
        return_value=_retro(),
    ) as mock_invoke:
        result = await run_retrospective(
            "S-1",
            {"rework_count": 2, "tokens": 50000},
            settings=settings,
        )
        assert result.sprint_id == "S-1"
        assert result.total_rework_cycles == 2
        assert len(result.improvements) == 1
        mock_invoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_retrospective_uses_validation_tier(settings: object) -> None:
    with patch(
        "colette.stages.retrospective.agent.invoke_structured",
        new_callable=AsyncMock,
        return_value=_retro(),
    ) as mock_invoke:
        await run_retrospective("S-1", {}, settings=settings)
        assert mock_invoke.call_args.kwargs["model_tier"].value == "validation"


@pytest.mark.asyncio
async def test_retrospective_includes_metrics_in_prompt(settings: object) -> None:
    with patch(
        "colette.stages.retrospective.agent.invoke_structured",
        new_callable=AsyncMock,
        return_value=_retro(),
    ) as mock_invoke:
        await run_retrospective(
            "S-1",
            {"gate_failures": 3, "human_overrides": 1},
            settings=settings,
        )
        user_content = mock_invoke.call_args.kwargs["user_content"]
        assert "gate_failures" in user_content
        assert "human_overrides" in user_content

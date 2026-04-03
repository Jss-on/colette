"""Tests for the triage agent (Phase 5)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from colette.schemas.backlog import BacklogPriority
from colette.schemas.bug import BugReport
from colette.stages.triage.agent import _SKIP_MAP, TriageResult, run_triage


def _bug(**overrides: object) -> BugReport:
    defaults: dict[str, object] = {
        "id": "BUG-001",
        "title": "App crash",
        "description": "Crash on empty input",
        "severity": BacklogPriority.P1_HIGH,
    }
    defaults.update(overrides)
    return BugReport(**defaults)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_run_triage_basic(settings: object) -> None:
    result = TriageResult(scope="implementation", root_cause_analysis="Null check")
    with patch(
        "colette.stages.triage.agent.invoke_structured",
        new_callable=AsyncMock,
        return_value=result,
    ) as mock_invoke:
        out = await run_triage(_bug(), settings=settings)
        assert out.scope == "implementation"
        assert out.skip_stages == ["requirements", "design"]
        mock_invoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_triage_design_scope(settings: object) -> None:
    result = TriageResult(scope="design")
    with patch(
        "colette.stages.triage.agent.invoke_structured",
        new_callable=AsyncMock,
        return_value=result,
    ):
        out = await run_triage(_bug(), settings=settings)
        assert out.skip_stages == ["requirements"]


@pytest.mark.asyncio
async def test_triage_testing_scope(settings: object) -> None:
    result = TriageResult(scope="testing")
    with patch(
        "colette.stages.triage.agent.invoke_structured",
        new_callable=AsyncMock,
        return_value=result,
    ):
        out = await run_triage(_bug(), settings=settings)
        assert "implementation" in out.skip_stages


@pytest.mark.asyncio
async def test_triage_requirements_scope(settings: object) -> None:
    result = TriageResult(scope="requirements")
    with patch(
        "colette.stages.triage.agent.invoke_structured",
        new_callable=AsyncMock,
        return_value=result,
    ):
        out = await run_triage(_bug(), settings=settings)
        assert out.skip_stages == []


def test_skip_map_completeness() -> None:
    assert "requirements" in _SKIP_MAP
    assert "design" in _SKIP_MAP
    assert "implementation" in _SKIP_MAP
    assert "testing" in _SKIP_MAP


@pytest.mark.asyncio
async def test_triage_includes_reproduction_steps(settings: object) -> None:
    result = TriageResult(scope="implementation")
    bug = _bug(reproduction_steps=["Step 1", "Step 2"])
    with patch(
        "colette.stages.triage.agent.invoke_structured",
        new_callable=AsyncMock,
        return_value=result,
    ) as mock_invoke:
        await run_triage(bug, settings=settings)
        user_content = mock_invoke.call_args.kwargs["user_content"]
        assert "Step 1" in user_content

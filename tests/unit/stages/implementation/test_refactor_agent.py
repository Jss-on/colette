"""Tests for the refactor agent — TDD REFACTOR phase (Phase 2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from colette.schemas.common import GeneratedFile
from colette.stages.implementation.refactor_agent import RefactorResult, run_refactor


def _file(path: str, content: str = "# code") -> GeneratedFile:
    return GeneratedFile(path=path, content=content, language="python")


@pytest.mark.asyncio
async def test_run_refactor_basic(settings: object) -> None:
    result = RefactorResult(
        refactored_files=[_file("src/api.py", "# cleaned")],
        changes_made=["Extracted duplicated validation"],
    )
    with patch(
        "colette.stages.implementation.refactor_agent.invoke_structured",
        new_callable=AsyncMock,
        return_value=result,
    ) as mock_invoke:
        out = await run_refactor(
            [_file("src/api.py"), _file("src/db.py")],
            [_file("tests/test_api.py")],
            settings=settings,
        )
        assert len(out.refactored_files) == 1
        assert out.refactored_files[0].content == "# cleaned"
        assert len(out.changes_made) == 1
        mock_invoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_refactor_empty_result(settings: object) -> None:
    result = RefactorResult()
    with patch(
        "colette.stages.implementation.refactor_agent.invoke_structured",
        new_callable=AsyncMock,
        return_value=result,
    ):
        out = await run_refactor([_file("a.py")], [_file("t.py")], settings=settings)
        assert out.refactored_files == []
        assert out.changes_made == []


@pytest.mark.asyncio
async def test_run_refactor_uses_execution_tier(settings: object) -> None:
    with patch(
        "colette.stages.implementation.refactor_agent.invoke_structured",
        new_callable=AsyncMock,
        return_value=RefactorResult(),
    ) as mock_invoke:
        await run_refactor([_file("a.py")], [_file("t.py")], settings=settings)
        call_kwargs = mock_invoke.call_args.kwargs
        assert call_kwargs["model_tier"].value == "execution"

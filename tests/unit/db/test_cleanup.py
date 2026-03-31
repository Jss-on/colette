"""Tests for stale run cleanup."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from colette.db.cleanup import cleanup_stale_runs
from colette.llm.registry import ProjectStatusRegistry


class _FakeRow:
    """Minimal stand-in for a SQLAlchemy result row."""

    def __init__(self, run_id: uuid.UUID, project_id: uuid.UUID) -> None:
        self.id = run_id
        self.project_id = project_id


@pytest.fixture
def fresh_registry():
    """Ensure the module-level registry is clean for each test."""
    fresh = ProjectStatusRegistry()
    import colette.db.cleanup as cleanup_mod
    import colette.llm.registry as reg_mod

    orig_reg = reg_mod.project_status_registry
    orig_cleanup = cleanup_mod.project_status_registry
    reg_mod.project_status_registry = fresh
    cleanup_mod.project_status_registry = fresh
    yield fresh
    reg_mod.project_status_registry = orig_reg
    cleanup_mod.project_status_registry = orig_cleanup


class TestCleanupStaleRuns:
    @pytest.mark.asyncio
    async def test_no_stale_runs_returns_zero(
        self, fresh_registry: ProjectStatusRegistry
    ) -> None:
        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = []
        session.execute = AsyncMock(return_value=result)

        count = await cleanup_stale_runs(session)
        assert count == 0

    @pytest.mark.asyncio
    async def test_cleans_stale_runs(
        self, fresh_registry: ProjectStatusRegistry
    ) -> None:
        pid = uuid.uuid4()
        stale = [_FakeRow(uuid.uuid4(), pid)]

        session = AsyncMock()
        select_result = MagicMock()
        select_result.all.return_value = stale
        session.execute = AsyncMock(return_value=select_result)
        session.commit = AsyncMock()

        count = await cleanup_stale_runs(session)
        assert count == 1
        assert fresh_registry.get(str(pid)) == "interrupted"

    @pytest.mark.asyncio
    async def test_marks_multiple_projects(
        self, fresh_registry: ProjectStatusRegistry
    ) -> None:
        pid1, pid2 = uuid.uuid4(), uuid.uuid4()
        stale = [
            _FakeRow(uuid.uuid4(), pid1),
            _FakeRow(uuid.uuid4(), pid2),
            _FakeRow(uuid.uuid4(), pid1),
        ]

        session = AsyncMock()
        select_result = MagicMock()
        select_result.all.return_value = stale
        session.execute = AsyncMock(return_value=select_result)
        session.commit = AsyncMock()

        count = await cleanup_stale_runs(session)
        assert count == 3
        assert fresh_registry.get(str(pid1)) == "interrupted"
        assert fresh_registry.get(str(pid2)) == "interrupted"

    @pytest.mark.asyncio
    async def test_calls_commit(
        self, fresh_registry: ProjectStatusRegistry
    ) -> None:
        stale = [_FakeRow(uuid.uuid4(), uuid.uuid4())]

        session = AsyncMock()
        select_result = MagicMock()
        select_result.all.return_value = stale
        session.execute = AsyncMock(return_value=select_result)
        session.commit = AsyncMock()

        await cleanup_stale_runs(session)
        session.commit.assert_awaited_once()

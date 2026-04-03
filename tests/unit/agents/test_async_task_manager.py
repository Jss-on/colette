"""Tests for async task manager (Phase 7c)."""

from __future__ import annotations

import asyncio

import pytest

from colette.agents.async_task_manager import AsyncTaskManager, TaskStatus
from colette.agents.subagent import SubAgentSpec


def _spec(name: str = "test") -> SubAgentSpec:
    return SubAgentSpec(name=name, description="", system_prompt="")


class TestAsyncTaskManager:
    @pytest.mark.asyncio
    async def test_start_task(self) -> None:
        mgr = AsyncTaskManager()
        handle = mgr.start_async_task(_spec(), {})
        assert handle.status in (TaskStatus.PENDING, TaskStatus.RUNNING)
        assert handle.task_id.startswith("task-")

    def test_check_nonexistent(self) -> None:
        mgr = AsyncTaskManager()
        assert mgr.check_task("fake") is None

    @pytest.mark.asyncio
    async def test_task_completes(self) -> None:
        mgr = AsyncTaskManager()
        handle = mgr.start_async_task(_spec(), {})
        await asyncio.sleep(0.1)  # let task run
        checked = mgr.check_task(handle.task_id)
        assert checked is not None
        assert checked.status == TaskStatus.COMPLETED

    def test_cancel_nonexistent(self) -> None:
        mgr = AsyncTaskManager()
        assert mgr.cancel_task("fake") is False

    def test_active_count_initial(self) -> None:
        mgr = AsyncTaskManager()
        assert mgr.active_count == 0

"""Async task manager for long-running cross-stage operations (Phase 7c)."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

from colette.agents.subagent import SubAgentSpec, spawn_subagent

logger = structlog.get_logger(__name__)


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskHandle:
    """Handle for tracking an async task."""

    task_id: str
    agent_name: str
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None


class AsyncTaskManager:
    """Manages long-running agent tasks with status tracking."""

    def __init__(self) -> None:
        self._tasks: dict[str, TaskHandle] = {}
        self._async_tasks: dict[str, asyncio.Task[None]] = {}

    def start_async_task(
        self,
        agent_spec: SubAgentSpec,
        context: dict[str, Any],
    ) -> TaskHandle:
        """Start an async task and return a handle for tracking."""
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        handle = TaskHandle(task_id=task_id, agent_name=agent_spec.name)
        self._tasks[task_id] = handle

        async def _run() -> None:
            handle.status = TaskStatus.RUNNING
            try:
                response = await spawn_subagent(agent_spec, context)
                handle.result = response.content
                handle.status = TaskStatus.COMPLETED
            except Exception as exc:
                handle.error = str(exc)
                handle.status = TaskStatus.FAILED
            finally:
                handle.completed_at = datetime.now(UTC)

        self._async_tasks[task_id] = asyncio.create_task(_run())
        return handle

    def check_task(self, task_id: str) -> TaskHandle | None:
        """Check the status of an async task."""
        return self._tasks.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running async task. Returns True if cancelled."""
        async_task = self._async_tasks.get(task_id)
        handle = self._tasks.get(task_id)
        if async_task and handle and handle.status == TaskStatus.RUNNING:
            async_task.cancel()
            handle.status = TaskStatus.CANCELLED
            handle.completed_at = datetime.now(UTC)
            return True
        return False

    @property
    def active_count(self) -> int:
        """Number of currently running tasks."""
        return sum(1 for h in self._tasks.values() if h.status == TaskStatus.RUNNING)

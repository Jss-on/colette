"""Pipeline runner — manages execution, concurrency, and checkpointing (FR-ORC-003/006)."""

from __future__ import annotations

import asyncio
import traceback as tb_mod
import uuid
from typing import Any

import structlog
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver

from colette.config import Settings
from colette.gates import create_default_registry
from colette.llm.registry import project_status_registry
from colette.orchestrator.event_bus import (
    EventType,
    PipelineEvent,
    PipelineEventBus,
    compute_elapsed,
)
from colette.orchestrator.pipeline import build_pipeline
from colette.orchestrator.progress import ProgressEvent, state_to_progress_event
from colette.orchestrator.state import create_initial_state

logger = structlog.get_logger()


class ConcurrencyLimitError(Exception):
    """Raised when the maximum number of concurrent pipelines is reached."""


class UserRequestTooLargeError(ValueError):
    """Raised when user_request exceeds the maximum allowed length."""


# Align with HandoffSchema.DEFAULT_MAX_HANDOFF_CHARS (32K chars ≈ 8K tokens).
MAX_USER_REQUEST_CHARS = 32_000


class PipelineRunner:
    """High-level API for starting, resuming, and monitoring pipelines.

    Parameters
    ----------
    settings:
        Application settings controlling checkpointer backend and concurrency.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        event_bus: PipelineEventBus | None = None,
    ) -> None:
        self._settings = settings or Settings()
        self._event_bus = event_bus or PipelineEventBus()

        # Checkpointer — MemorySaver for dev; PostgresSaver for prod.
        self._checkpointer = self._create_checkpointer()

        # Build the compiled pipeline graph once.
        self._gate_registry = create_default_registry()
        self._graph = build_pipeline(
            self._gate_registry,
            self._settings,
            checkpointer=self._checkpointer,
            event_bus=self._event_bus,
        )

        # Track active pipeline runs (project_id -> thread_id).
        self._active: dict[str, str] = {}

        # Track asyncio tasks for hard cancellation.
        self._tasks: dict[str, asyncio.Task[Any]] = {}

    def _create_checkpointer(self) -> MemorySaver:
        """Create the checkpoint backend.

        Uses ``MemorySaver`` for dev/test (default) and
        ``PostgresSaver`` for production when ``checkpoint_backend="postgres"``.
        """
        if self._settings.checkpoint_backend == "postgres":
            try:
                from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

                db_url = self._settings.checkpoint_db_url or self._settings.database_url
                # Convert asyncpg URL to psycopg for checkpoint library.
                sync_url = db_url.replace("+asyncpg", "+psycopg")
                return AsyncPostgresSaver.from_conn_string(sync_url)  # type: ignore[no-any-return]
            except ImportError:
                logger.warning(
                    "langgraph-checkpoint-postgres not installed; falling back to MemorySaver"
                )
        return MemorySaver()

    @property
    def event_bus(self) -> PipelineEventBus:
        """The event bus used by this runner for pipeline progress events."""
        return self._event_bus

    # ── Public API ───────────────────────────────────────────────────

    async def run(
        self,
        project_id: str,
        *,
        user_request: str = "",
        skip_stages: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Start a new pipeline run for *project_id*.

        Parameters
        ----------
        user_request:
            Natural language project description from the user (FR-REQ-001).

        Raises ``ConcurrencyLimitExceeded`` if the concurrent-pipeline
        limit has been reached.
        """
        if len(user_request) > MAX_USER_REQUEST_CHARS:
            msg = (
                f"user_request exceeds maximum length "
                f"({len(user_request)} > {MAX_USER_REQUEST_CHARS} chars)"
            )
            raise UserRequestTooLargeError(msg)

        if len(self._active) >= self._settings.max_concurrent_pipelines:
            msg = (
                f"Concurrent pipeline limit ({self._settings.max_concurrent_pipelines}) "
                "reached — wait for an existing run to finish."
            )
            raise ConcurrencyLimitError(msg)

        thread_id = f"{project_id}-{uuid.uuid4().hex[:8]}"
        self._active[project_id] = thread_id

        # Register as running — enables LLM API calls for this project.
        project_status_registry.mark(project_id, "running")

        initial = create_initial_state(
            project_id,
            pipeline_run_id=thread_id,
            user_request=user_request,
        )
        if skip_stages:
            initial["skip_stages"] = skip_stages
        if metadata:
            initial["metadata"] = metadata

        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        logger.info("pipeline.start", project_id=project_id, thread_id=thread_id)

        try:
            result = await self._graph.ainvoke(dict(initial), config)
            project_status_registry.mark(project_id, "completed")
            self._event_bus.emit(
                PipelineEvent(
                    project_id=project_id,
                    event_type=EventType.PIPELINE_COMPLETED,
                    elapsed_seconds=compute_elapsed(initial["started_at"]),
                )
            )
            return dict(result)
        except Exception as exc:
            project_status_registry.mark(project_id, "failed")
            self._event_bus.emit(
                PipelineEvent(
                    project_id=project_id,
                    event_type=EventType.PIPELINE_FAILED,
                    message=str(exc),
                    detail={"traceback": tb_mod.format_exc()},
                    elapsed_seconds=compute_elapsed(initial["started_at"]),
                )
            )
            raise
        finally:
            self._active.pop(project_id, None)
            self._tasks.pop(project_id, None)

    async def resume(
        self,
        project_id: str,
        update_values: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Resume a paused pipeline (e.g. after human approval)."""
        thread_id = self._active.get(project_id)
        if not thread_id:
            msg = f"No active pipeline found for project '{project_id}'"
            raise KeyError(msg)

        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        result = await self._graph.ainvoke(update_values, config)
        return dict(result)

    async def get_progress(self, project_id: str) -> ProgressEvent:
        """Read the current progress of a running pipeline."""
        thread_id = self._active.get(project_id)
        if not thread_id:
            msg = f"No active pipeline found for project '{project_id}'"
            raise KeyError(msg)

        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        snapshot = await self._graph.aget_state(config)
        return state_to_progress_event(dict(snapshot.values))

    def register_task(self, project_id: str, task: asyncio.Task[Any]) -> None:
        """Register an asyncio task for *project_id* (enables hard cancellation)."""
        self._tasks[project_id] = task

    def cancel_project(self, project_id: str, *, status: str = "interrupted") -> bool:
        """Hard-cancel a running pipeline and block its LLM calls.

        Returns ``True`` if a task was cancelled, ``False`` if no active task
        was found for *project_id*.
        """
        project_status_registry.mark(project_id, status)

        task = self._tasks.pop(project_id, None)
        self._active.pop(project_id, None)

        if task is not None and not task.done():
            task.cancel()
            logger.warning("pipeline.cancelled", project_id=project_id, status=status)
            return True

        logger.info("pipeline.cancel_no_task", project_id=project_id, status=status)
        return False

    def active_pipeline_count(self) -> int:
        """Return the number of currently active pipelines."""
        return len(self._active)

    def is_active(self, project_id: str) -> bool:
        """Check whether *project_id* has an active pipeline."""
        return project_id in self._active

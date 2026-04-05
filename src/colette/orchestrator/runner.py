"""Pipeline runner — manages execution, concurrency, and checkpointing (FR-ORC-003/006)."""

from __future__ import annotations

import asyncio
import traceback as tb_mod
import uuid
from typing import Any

import structlog
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import GraphInterrupt
from langgraph.types import Command

from colette.config import Settings
from colette.gates import create_default_registry
from colette.llm.registry import project_status_registry
from colette.orchestrator.event_bus import (
    EventType,
    PipelineEvent,
    PipelineEventBus,
    compute_elapsed,
)
from colette.orchestrator.progress import ProgressEvent, state_to_progress_event
from colette.orchestrator.state import create_initial_state

logger = structlog.get_logger()


class _AsyncWrappedPostgresSaver(MemorySaver):
    """Wraps sync ``PostgresSaver`` with async methods via ``run_in_executor``.

    psycopg async is incompatible with Windows ``ProactorEventLoop``, so we
    keep the sync driver and offload blocking calls to a thread pool.  This
    satisfies LangGraph >=1.1 which requires ``aget_tuple`` / ``aput`` etc.

    Inherits from ``MemorySaver`` only for type compatibility with
    ``BaseCheckpointSaver``; all operations delegate to the inner
    ``PostgresSaver``.
    """

    def __init__(self, conn_or_pool: Any) -> None:
        super().__init__()
        from langgraph.checkpoint.postgres import PostgresSaver

        self._inner = PostgresSaver(conn_or_pool)

    # Delegate attribute access to the inner saver for config_specs, serde, etc.
    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    async def _run(self, method: str, *args: Any, **kwargs: Any) -> Any:
        loop = asyncio.get_running_loop()
        func = getattr(self._inner, method)
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    # ── Sync interface (delegates to inner PostgresSaver) ────────────
    def get_tuple(self, config: Any) -> Any:
        return self._inner.get_tuple(config)

    def put(self, config: Any, checkpoint: Any, metadata: Any, new_versions: Any) -> Any:
        return self._inner.put(config, checkpoint, metadata, new_versions)

    def put_writes(
        self,
        config: Any,
        writes: Any,
        task_id: Any,
        task_path: str = "",
    ) -> None:
        self._inner.put_writes(config, writes, task_id, task_path)

    def list(self, config: Any, **kwargs: Any) -> Any:
        return self._inner.list(config, **kwargs)

    # ── Async interface required by LangGraph ────────────────────────
    async def aget_tuple(self, config: Any) -> Any:
        return await self._run("get_tuple", config)

    async def aput(self, config: Any, checkpoint: Any, metadata: Any, new_versions: Any) -> Any:
        return await self._run("put", config, checkpoint, metadata, new_versions)

    async def aput_writes(
        self,
        config: Any,
        writes: Any,
        task_id: Any,
        task_path: str = "",
    ) -> None:
        await self._run("put_writes", config, writes, task_id, task_path)

    async def alist(self, config: Any, **kwargs: Any) -> Any:
        loop = asyncio.get_running_loop()
        items = await loop.run_in_executor(None, lambda: list(self._inner.list(config, **kwargs)))
        for item in items:
            yield item

    def setup(self) -> None:
        self._inner.setup()


class ConcurrencyLimitError(Exception):
    """Raised when the maximum number of concurrent pipelines is reached."""


class UserRequestTooLargeError(ValueError):
    """Raised when user_request exceeds the maximum allowed length."""


# Align with HandoffSchema.DEFAULT_MAX_HANDOFF_CHARS (128K chars ≈ 32K tokens).
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
        self._checkpointer: MemorySaver | Any = MemorySaver()
        self._pg_pool: Any | None = None  # ConnectionPool, set by asetup()

        # Build the compiled pipeline graph once (re-built after asetup if needed).
        from colette.orchestrator.pipeline import build_pipeline

        self._gate_registry = create_default_registry(self._settings)
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

    async def asetup(self) -> None:
        """Async initialisation — call once at application startup.

        When ``checkpoint_backend="postgres"``, opens a sync connection
        pool, creates checkpoint tables, and rebuilds the pipeline graph
        with the durable checkpointer.  No-op for the default memory
        backend.

        Uses the **sync** ``PostgresSaver`` (not async) to avoid Windows
        ``ProactorEventLoop`` incompatibility with psycopg async.
        """
        if self._settings.checkpoint_backend != "postgres":
            return

        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            from psycopg import Connection
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool
        except ImportError:
            logger.warning(
                "langgraph-checkpoint-postgres not installed; falling back to MemorySaver"
            )
            return

        db_url = self._settings.checkpoint_db_url or self._settings.database_url
        # psycopg needs a plain postgresql:// URL, not asyncpg.
        conn_str = db_url.replace("+asyncpg", "")

        # Create tables with an autocommit connection (required for
        # CREATE INDEX CONCURRENTLY in the migration).
        setup_conn = Connection.connect(
            conn_str,
            autocommit=True,
            row_factory=dict_row,
        )
        try:
            PostgresSaver(setup_conn).setup()
        finally:
            setup_conn.close()

        # Open a connection pool for runtime use.
        self._pg_pool = ConnectionPool(conn_str)
        self._checkpointer = _AsyncWrappedPostgresSaver(self._pg_pool)

        # Rebuild the graph with the durable checkpointer.
        from colette.orchestrator.pipeline import build_pipeline

        self._graph = build_pipeline(
            self._gate_registry,
            self._settings,
            checkpointer=self._checkpointer,
            event_bus=self._event_bus,
        )
        logger.info("checkpoint.postgres_ready")

    async def ashutdown(self) -> None:
        """Close the Postgres connection pool (if any)."""
        if self._pg_pool is not None:
            self._pg_pool.close()
            self._pg_pool = None

    @property
    def event_bus(self) -> PipelineEventBus:
        """The event bus used by this runner for pipeline progress events."""
        return self._event_bus

    @staticmethod
    def _extract_interrupt_approval(snapshot: Any) -> list[dict[str, Any]]:
        """Extract approval requests from the LangGraph interrupt payload.

        When a gate node calls ``interrupt(approval_req)``, the payload
        is stored in the checkpoint but the node's return dict (which
        would contain ``approval_requests``) is never applied to the
        pipeline state.  This helper recovers the approval data from
        ``snapshot.tasks[*].interrupts[*].value`` so callers can persist
        it to the database.
        """
        approval_requests: list[dict[str, Any]] = []
        for task in getattr(snapshot, "tasks", ()):
            for intr in getattr(task, "interrupts", ()):
                val = getattr(intr, "value", None)
                if isinstance(val, dict) and "request_id" in val:
                    approval_requests.append(val)
        return approval_requests

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

            # With a checkpointer, LangGraph may return normally on
            # interrupt() instead of raising GraphInterrupt.  Detect
            # this by checking whether the graph has pending nodes.
            snapshot = await self._graph.aget_state(config)
            if snapshot.next:
                project_status_registry.mark(project_id, "awaiting_approval")
                logger.info("pipeline.awaiting_approval", project_id=project_id)
                state = dict(snapshot.values)
                # Inject interrupt-payload approvals into state so
                # callers can persist them (gate node never returns).
                interrupt_approvals = self._extract_interrupt_approval(snapshot)
                if interrupt_approvals:
                    state["approval_requests"] = interrupt_approvals
                return state

            project_status_registry.mark(project_id, "completed")
            self._event_bus.emit(
                PipelineEvent(
                    project_id=project_id,
                    event_type=EventType.PIPELINE_COMPLETED,
                    elapsed_seconds=compute_elapsed(initial["started_at"]),
                )
            )
            return dict(result)
        except GraphInterrupt:
            # Fallback for configs without a checkpointer.
            project_status_registry.mark(project_id, "awaiting_approval")
            logger.info("pipeline.awaiting_approval", project_id=project_id)
            snapshot = await self._graph.aget_state(config)
            state = dict(snapshot.values)
            interrupt_approvals = self._extract_interrupt_approval(snapshot)
            if interrupt_approvals:
                state["approval_requests"] = interrupt_approvals
            return state
        except Exception as exc:
            logger.error(
                "pipeline.ainvoke_failed",
                project_id=project_id,
                exc_type=type(exc).__name__,
                exc_repr=repr(exc),
                traceback=tb_mod.format_exc(),
            )
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
            # Don't remove from _active if awaiting approval
            status = project_status_registry.get(project_id)
            if status != "awaiting_approval":
                self._active.pop(project_id, None)
                self._tasks.pop(project_id, None)

    async def resume(
        self,
        project_id: str,
        update_values: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Resume a paused pipeline (e.g. after human approval).

        Uses LangGraph's ``Command(resume=...)`` to continue from
        the ``interrupt()`` point in the gate node.
        """
        thread_id = self._active.get(project_id)
        if not thread_id:
            msg = f"No active pipeline found for project '{project_id}'"
            raise KeyError(msg)

        project_status_registry.mark(project_id, "running")
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

        approval_value = update_values or {"action": "approved"}
        logger.info("pipeline.resume", project_id=project_id)

        try:
            result = await self._graph.ainvoke(Command(resume=approval_value), config)

            # Check if the graph hit another interrupt.
            snapshot = await self._graph.aget_state(config)
            if snapshot.next:
                project_status_registry.mark(project_id, "awaiting_approval")
                logger.info("pipeline.awaiting_approval", project_id=project_id)
                state = dict(snapshot.values)
                interrupt_approvals = self._extract_interrupt_approval(snapshot)
                if interrupt_approvals:
                    state["approval_requests"] = interrupt_approvals
                return state

            project_status_registry.mark(project_id, "completed")
            self._event_bus.emit(
                PipelineEvent(
                    project_id=project_id,
                    event_type=EventType.PIPELINE_COMPLETED,
                    elapsed_seconds=compute_elapsed(result.get("started_at", "")),
                )
            )
            return dict(result)
        except GraphInterrupt:
            # Fallback for configs without a checkpointer.
            project_status_registry.mark(project_id, "awaiting_approval")
            logger.info("pipeline.awaiting_approval", project_id=project_id)
            snapshot = await self._graph.aget_state(config)
            state = dict(snapshot.values)
            interrupt_approvals = self._extract_interrupt_approval(snapshot)
            if interrupt_approvals:
                state["approval_requests"] = interrupt_approvals
            return state
        except Exception:
            project_status_registry.mark(project_id, "failed")
            self._active.pop(project_id, None)
            self._tasks.pop(project_id, None)
            raise

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

    def is_awaiting_approval(self, project_id: str) -> bool:
        """Check whether *project_id* is paused at an approval gate."""
        return (
            project_id in self._active
            and project_status_registry.get(project_id) == "awaiting_approval"
        )

    def rehydrate(self, project_id: str, thread_id: str) -> None:
        """Re-register a paused pipeline in ``_active`` (e.g. after server restart).

        This allows ``resume()`` to find the pipeline's thread_id without
        requiring it to still be in the in-memory dict.  The checkpointer
        must still hold the graph state for this to work.
        """
        self._active[project_id] = thread_id
        project_status_registry.mark(project_id, "awaiting_approval")
        logger.info(
            "pipeline.rehydrated",
            project_id=project_id,
            thread_id=thread_id,
        )

    def get_thread_id(self, project_id: str) -> str | None:
        """Return the thread_id for *project_id*, or ``None``."""
        return self._active.get(project_id)

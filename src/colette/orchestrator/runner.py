"""Pipeline runner — manages execution, concurrency, and checkpointing (FR-ORC-003/006)."""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver

from colette.config import Settings
from colette.gates import create_default_registry
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

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()

        # Checkpointer — MemorySaver for dev; PostgresSaver for prod.
        self._checkpointer = self._create_checkpointer()

        # Build the compiled pipeline graph once.
        self._gate_registry = create_default_registry()
        self._graph = build_pipeline(
            self._gate_registry,
            self._settings,
            checkpointer=self._checkpointer,
        )

        # Track active pipeline runs (project_id -> thread_id).
        self._active: dict[str, str] = {}

    def _create_checkpointer(self) -> MemorySaver:
        """Create the checkpoint backend.

        PostgresSaver support is deferred to Phase 8 — for now, always
        use ``MemorySaver`` which is sufficient for dev and testing.
        """
        return MemorySaver()

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

        initial = create_initial_state(
            project_id, pipeline_run_id=thread_id, user_request=user_request,
        )
        if skip_stages:
            initial["skip_stages"] = skip_stages
        if metadata:
            initial["metadata"] = metadata

        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        logger.info("pipeline.start", project_id=project_id, thread_id=thread_id)

        try:
            result = await self._graph.ainvoke(dict(initial), config)
            return dict(result)
        finally:
            self._active.pop(project_id, None)

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

    def active_pipeline_count(self) -> int:
        """Return the number of currently active pipelines."""
        return len(self._active)

    def is_active(self, project_id: str) -> bool:
        """Check whether *project_id* has an active pipeline."""
        return project_id in self._active

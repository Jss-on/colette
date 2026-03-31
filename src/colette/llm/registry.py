"""In-memory project status registry — gates LLM API access.

Only projects with status ``"running"`` are allowed to make LLM calls.
This prevents catastrophic API spend from interrupted or cancelled pipelines
that somehow keep executing.
"""

from __future__ import annotations

import threading

import structlog

logger = structlog.get_logger(__name__)


class ProjectNotActiveError(RuntimeError):
    """Raised when an LLM call is attempted for a non-running project."""


class ProjectStatusRegistry:
    """In-memory gate. Only ``'running'`` projects may call LLMs.

    Thread-safe via a lock — the registry is shared across async tasks
    and potentially across threads in a multi-worker setup.
    """

    def __init__(self) -> None:
        self._statuses: dict[str, str] = {}
        self._lock = threading.Lock()

    def assert_active(self, project_id: str) -> None:
        """Raise ``ProjectNotActiveError`` if *project_id* is not running."""
        with self._lock:
            status = self._statuses.get(project_id)
        if status != "running":
            raise ProjectNotActiveError(
                f"Project {project_id} is '{status}' — LLM calls blocked. "
                f"Use 'colette resume {project_id}' to reactivate."
            )

    def mark(self, project_id: str, status: str) -> None:
        """Set the status for *project_id*."""
        with self._lock:
            self._statuses[project_id] = status
        logger.info(
            "project_status_changed",
            project_id=project_id,
            status=status,
        )

    def get(self, project_id: str) -> str | None:
        """Return the current status, or ``None`` if unknown."""
        with self._lock:
            return self._statuses.get(project_id)

    def remove(self, project_id: str) -> None:
        """Remove a project from the registry (e.g. after completion)."""
        with self._lock:
            self._statuses.pop(project_id, None)

    def running_count(self) -> int:
        """Return the number of projects currently marked as running."""
        with self._lock:
            return sum(1 for s in self._statuses.values() if s == "running")


# Module-level singleton — imported throughout the application.
project_status_registry = ProjectStatusRegistry()

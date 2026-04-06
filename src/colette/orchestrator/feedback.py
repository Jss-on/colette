"""Operator feedback manager for real-time intervention during pipeline execution."""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class OperatorMessage:
    """A message from the operator to a specific agent."""

    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class OperatorFeedbackManager:
    """Thread-safe manager for operator messages to agents.

    Messages are queued per-agent and consumed by the agent's next LLM call
    via the callback handler.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Key: "{project_id}:{agent_id}" -> list of pending messages
        self._queues: dict[str, list[OperatorMessage]] = defaultdict(list)

    def enqueue(self, project_id: str, agent_id: str, message: str) -> None:
        """Queue a message for delivery to a specific agent."""
        key = f"{project_id}:{agent_id}"
        with self._lock:
            self._queues[key].append(OperatorMessage(message=message))

    def drain(self, project_id: str, agent_id: str) -> list[OperatorMessage]:
        """Consume all pending messages for an agent (FIFO)."""
        key = f"{project_id}:{agent_id}"
        with self._lock:
            messages = self._queues.pop(key, [])
        return messages

    def has_pending(self, project_id: str, agent_id: str) -> bool:
        """Check if an agent has pending messages."""
        key = f"{project_id}:{agent_id}"
        with self._lock:
            return bool(self._queues.get(key))

    def clear_project(self, project_id: str) -> None:
        """Remove all queued messages for a project."""
        prefix = f"{project_id}:"
        with self._lock:
            keys_to_remove = [k for k in self._queues if k.startswith(prefix)]
            for k in keys_to_remove:
                del self._queues[k]


# Module-level singleton
operator_feedback_manager = OperatorFeedbackManager()

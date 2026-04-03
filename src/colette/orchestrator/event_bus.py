"""In-process event bus for pipeline progress events (Phase 2)."""

from __future__ import annotations

import asyncio
import contextlib
from collections import defaultdict
from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

__all__ = [
    "EventType",
    "PipelineEvent",
    "PipelineEventBus",
    "compute_elapsed",
    "event_bus_var",
    "project_id_var",
    "stage_var",
]

# ── Async-safe context variables for event bus propagation ────────────
# Set in pipeline stage nodes; read by callbacks and structured LLM calls
# so agent-level events flow to the bus without changing every signature.
event_bus_var: ContextVar[PipelineEventBus | None] = ContextVar("event_bus_var", default=None)
project_id_var: ContextVar[str] = ContextVar("project_id_var", default="")
stage_var: ContextVar[str] = ContextVar("stage_var", default="")

MAX_QUEUE_SIZE = 1000


class EventType(StrEnum):
    """Pipeline event types emitted during execution."""

    STAGE_STARTED = "stage_started"
    STAGE_COMPLETED = "stage_completed"
    STAGE_FAILED = "stage_failed"
    GATE_PASSED = "gate_passed"
    GATE_FAILED = "gate_failed"
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    AGENT_ERROR = "agent_error"
    AGENT_THINKING = "agent_thinking"
    AGENT_TOOL_CALL = "agent_tool_call"
    AGENT_REVIEWING = "agent_reviewing"
    AGENT_HANDOFF = "agent_handoff"
    AGENT_MESSAGE = "agent_message"
    AGENT_STREAM_CHUNK = "agent_stream_chunk"
    AGENT_STATE_CHANGED = "agent_state_changed"
    APPROVAL_REQUIRED = "approval_required"
    FEEDBACK_APPLIED = "feedback_applied"
    PIPELINE_COMPLETED = "pipeline_completed"
    PIPELINE_FAILED = "pipeline_failed"


@dataclass(frozen=True)
class PipelineEvent:
    """A single pipeline execution event."""

    project_id: str
    event_type: EventType
    stage: str = ""
    agent: str = ""
    model: str = ""
    message: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    elapsed_seconds: float = 0.0
    tokens_used: int = 0


class PipelineEventBus:
    """In-process event bus for pipeline progress events.

    Subscribers get a per-project ``asyncio.Queue``.  Events are dispatched
    non-blocking — if a subscriber's queue is full, the event is dropped
    with a warning log.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue[PipelineEvent]]] = defaultdict(list)

    def subscribe(
        self, project_id: str, *, max_size: int = MAX_QUEUE_SIZE
    ) -> asyncio.Queue[PipelineEvent]:
        """Create a subscription queue for *project_id* events."""
        queue: asyncio.Queue[PipelineEvent] = asyncio.Queue(maxsize=max_size)
        self._subscribers[project_id].append(queue)
        return queue

    def unsubscribe(self, project_id: str, queue: asyncio.Queue[PipelineEvent]) -> None:
        """Remove a subscriber queue.  Safe to call even if not subscribed."""
        queues = self._subscribers.get(project_id, [])
        with contextlib.suppress(ValueError):
            queues.remove(queue)
        if not queues:
            self._subscribers.pop(project_id, None)

    def emit(self, event: PipelineEvent) -> None:
        """Broadcast *event* to all subscribers of its project.

        Non-blocking.  Drops the event for any subscriber whose queue is full.
        """
        for queue in list(self._subscribers.get(event.project_id, [])):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "event_bus.queue_full",
                    project_id=event.project_id,
                    event_type=event.event_type.value,
                )

    def subscriber_count(self, project_id: str) -> int:
        """Return the number of active subscribers for *project_id*."""
        return len(self._subscribers.get(project_id, []))


def compute_elapsed(started_at: str) -> float:
    """Compute seconds elapsed since *started_at* ISO timestamp."""
    if not started_at:
        return 0.0
    try:
        start_dt = datetime.fromisoformat(started_at)
        return (datetime.now(UTC) - start_dt).total_seconds()
    except (ValueError, TypeError):
        return 0.0

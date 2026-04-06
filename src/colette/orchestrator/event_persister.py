"""Persist pipeline events to database for history and replay."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable, Coroutine
from typing import Any

import structlog

from colette.orchestrator.event_bus import EventType, PipelineEvent

logger = structlog.get_logger(__name__)

# Event types that are too high-volume or ephemeral to persist.
_SKIP_TYPES: frozenset[EventType] = frozenset(
    {
        EventType.AGENT_STREAM_CHUNK,
    }
)


class EventPersister:
    """Subscribes to the event bus and persists events to the database in batches.

    Parameters
    ----------
    write_fn:
        Async callable that accepts a list of PipelineEvent dicts and writes
        them to the database.  This decouples the persister from the ORM layer.
    batch_size:
        Maximum events to accumulate before flushing.
    flush_interval:
        Seconds between automatic flushes.
    """

    def __init__(
        self,
        write_fn: Callable[[list[dict[str, Any]]], Coroutine[Any, Any, None]],
        batch_size: int = 50,
        flush_interval: float = 0.5,
    ) -> None:
        self._write_fn = write_fn
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._batch: list[dict[str, Any]] = []
        self._flush_task: asyncio.Task[None] | None = None

    async def handle(self, event: PipelineEvent) -> None:
        """Receive an event from the bus."""
        if event.event_type in _SKIP_TYPES:
            return

        self._batch.append(
            {
                "project_id": event.project_id,
                "event_type": event.event_type.value,
                "stage": event.stage,
                "agent": event.agent,
                "model": event.model,
                "message": event.message,
                "detail": dict(event.detail),
                "elapsed_seconds": event.elapsed_seconds,
                "tokens_used": event.tokens_used,
                "timestamp": event.timestamp.isoformat(),
            }
        )

        if len(self._batch) >= self._batch_size:
            await self._flush()

    async def start(self) -> None:
        """Start the periodic flush loop."""
        self._flush_task = asyncio.create_task(self._periodic_flush())

    async def stop(self) -> None:
        """Stop the periodic flush loop and drain remaining events."""
        if self._flush_task:
            self._flush_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._flush_task
        await self._flush()

    async def _periodic_flush(self) -> None:
        """Flush at regular intervals."""
        while True:
            await asyncio.sleep(self._flush_interval)
            await self._flush()

    async def _flush(self) -> None:
        """Write accumulated events to the database."""
        if not self._batch:
            return

        batch = self._batch
        self._batch = []

        try:
            await self._write_fn(batch)
        except Exception:
            logger.exception("event_persister_flush_failed", count=len(batch))
            # Re-queue failed events (drop if batch grows too large)
            if len(self._batch) < self._batch_size * 10:
                self._batch = batch + self._batch

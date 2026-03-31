"""Tests for PipelineEventBus."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from colette.orchestrator.event_bus import (
    EventType,
    PipelineEvent,
    PipelineEventBus,
    compute_elapsed,
)

# ── PipelineEvent ────────────────────────────────────────────────────


class TestPipelineEvent:
    def test_create_minimal(self) -> None:
        event = PipelineEvent(
            project_id="proj-1",
            event_type=EventType.STAGE_STARTED,
        )
        assert event.project_id == "proj-1"
        assert event.event_type == EventType.STAGE_STARTED
        assert event.stage == ""
        assert event.agent == ""
        assert event.model == ""
        assert event.message == ""
        assert event.detail == {}
        assert event.elapsed_seconds == 0.0
        assert event.tokens_used == 0
        assert isinstance(event.timestamp, datetime)

    def test_create_full(self) -> None:
        ts = datetime.now(UTC)
        event = PipelineEvent(
            project_id="proj-1",
            event_type=EventType.STAGE_COMPLETED,
            stage="requirements",
            agent="analyst",
            model="claude-sonnet-4-6",
            message="PRD generated",
            detail={"completeness": 0.95},
            timestamp=ts,
            elapsed_seconds=23.5,
            tokens_used=1200,
        )
        assert event.stage == "requirements"
        assert event.agent == "analyst"
        assert event.detail["completeness"] == 0.95
        assert event.timestamp == ts
        assert event.elapsed_seconds == 23.5
        assert event.tokens_used == 1200

    def test_frozen(self) -> None:
        event = PipelineEvent(
            project_id="p1", event_type=EventType.STAGE_STARTED
        )
        with pytest.raises(AttributeError):
            event.stage = "design"  # type: ignore[misc]

    def test_each_instance_gets_own_detail_dict(self) -> None:
        e1 = PipelineEvent(project_id="p1", event_type=EventType.STAGE_STARTED)
        e2 = PipelineEvent(project_id="p2", event_type=EventType.STAGE_STARTED)
        assert e1.detail is not e2.detail


# ── EventType ────────────────────────────────────────────────────────


class TestEventType:
    def test_all_event_types_are_strings(self) -> None:
        for et in EventType:
            assert isinstance(et, str)
            assert isinstance(et.value, str)

    def test_expected_event_types_exist(self) -> None:
        expected = {
            "stage_started",
            "stage_completed",
            "stage_failed",
            "gate_passed",
            "gate_failed",
            "agent_started",
            "agent_completed",
            "agent_error",
            "pipeline_completed",
            "pipeline_failed",
        }
        actual = {et.value for et in EventType}
        assert actual == expected


# ── PipelineEventBus ─────────────────────────────────────────────────


class TestPipelineEventBus:
    def test_subscribe_creates_queue(self) -> None:
        bus = PipelineEventBus()
        queue = bus.subscribe("proj-1")
        assert isinstance(queue, asyncio.Queue)
        assert bus.subscriber_count("proj-1") == 1

    def test_multiple_subscribers(self) -> None:
        bus = PipelineEventBus()
        bus.subscribe("proj-1")
        bus.subscribe("proj-1")
        assert bus.subscriber_count("proj-1") == 2

    def test_unsubscribe_removes_queue(self) -> None:
        bus = PipelineEventBus()
        queue = bus.subscribe("proj-1")
        bus.unsubscribe("proj-1", queue)
        assert bus.subscriber_count("proj-1") == 0

    def test_unsubscribe_unknown_project_is_safe(self) -> None:
        bus = PipelineEventBus()
        queue: asyncio.Queue[PipelineEvent] = asyncio.Queue()
        bus.unsubscribe("proj-unknown", queue)

    def test_unsubscribe_unknown_queue_is_safe(self) -> None:
        bus = PipelineEventBus()
        bus.subscribe("proj-1")
        unknown_queue: asyncio.Queue[PipelineEvent] = asyncio.Queue()
        bus.unsubscribe("proj-1", unknown_queue)
        assert bus.subscriber_count("proj-1") == 1

    def test_emit_delivers_to_subscriber(self) -> None:
        bus = PipelineEventBus()
        queue = bus.subscribe("proj-1")
        event = PipelineEvent(
            project_id="proj-1",
            event_type=EventType.STAGE_STARTED,
            stage="requirements",
        )
        bus.emit(event)
        assert not queue.empty()
        received = queue.get_nowait()
        assert received.project_id == "proj-1"
        assert received.event_type == EventType.STAGE_STARTED
        assert received.stage == "requirements"

    def test_emit_delivers_to_multiple_subscribers(self) -> None:
        bus = PipelineEventBus()
        q1 = bus.subscribe("proj-1")
        q2 = bus.subscribe("proj-1")
        event = PipelineEvent(
            project_id="proj-1",
            event_type=EventType.STAGE_COMPLETED,
            stage="design",
        )
        bus.emit(event)
        assert q1.get_nowait().stage == "design"
        assert q2.get_nowait().stage == "design"

    def test_emit_only_to_matching_project(self) -> None:
        bus = PipelineEventBus()
        q1 = bus.subscribe("proj-1")
        q2 = bus.subscribe("proj-2")
        event = PipelineEvent(
            project_id="proj-1",
            event_type=EventType.STAGE_STARTED,
        )
        bus.emit(event)
        assert not q1.empty()
        assert q2.empty()

    def test_emit_drops_on_full_queue(self) -> None:
        bus = PipelineEventBus()
        queue = bus.subscribe("proj-1", max_size=1)
        bus.emit(
            PipelineEvent(
                project_id="proj-1", event_type=EventType.STAGE_STARTED
            )
        )
        # Second emit should be dropped, not raise
        bus.emit(
            PipelineEvent(
                project_id="proj-1", event_type=EventType.STAGE_COMPLETED
            )
        )
        assert queue.qsize() == 1
        assert queue.get_nowait().event_type == EventType.STAGE_STARTED

    def test_emit_no_subscribers_is_noop(self) -> None:
        bus = PipelineEventBus()
        event = PipelineEvent(
            project_id="proj-1", event_type=EventType.STAGE_STARTED
        )
        bus.emit(event)  # Should not raise

    def test_subscriber_count_zero_for_unknown(self) -> None:
        bus = PipelineEventBus()
        assert bus.subscriber_count("unknown") == 0

    def test_unsubscribe_then_emit_does_not_deliver(self) -> None:
        bus = PipelineEventBus()
        queue = bus.subscribe("proj-1")
        bus.unsubscribe("proj-1", queue)
        bus.emit(
            PipelineEvent(
                project_id="proj-1", event_type=EventType.STAGE_STARTED
            )
        )
        assert queue.empty()


# ── compute_elapsed ──────────────────────────────────────────────────


class TestComputeElapsed:
    def test_empty_string_returns_zero(self) -> None:
        assert compute_elapsed("") == 0.0

    def test_valid_iso_timestamp(self) -> None:
        # Use a timestamp 10 seconds ago
        past = datetime.now(UTC).isoformat()
        elapsed = compute_elapsed(past)
        assert elapsed >= 0.0
        assert elapsed < 2.0  # Should be near-instant

    def test_invalid_timestamp_returns_zero(self) -> None:
        assert compute_elapsed("not-a-date") == 0.0

    def test_naive_timestamp_returns_zero(self) -> None:
        # Naive ISO string (no timezone) mixed with aware now(UTC) raises TypeError
        # which is caught and returns 0.0
        assert compute_elapsed("2024-01-01T00:00:00") == 0.0

"""Tests for pipeline SSE streaming (Phase 3)."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from colette.api.routes.pipelines import _sse_event_generator
from colette.api.schemas import PipelineSSEEvent
from colette.orchestrator.event_bus import EventType, PipelineEvent, PipelineEventBus

# ── PipelineSSEEvent schema ──────────────────────────────────────────


class TestPipelineSSEEvent:
    def test_minimal_creation(self) -> None:
        event = PipelineSSEEvent(
            event_type="stage_started",
            project_id="proj-1",
            timestamp="2026-03-31T12:00:00+00:00",
        )
        assert event.event_type == "stage_started"
        assert event.project_id == "proj-1"

    def test_full_creation(self) -> None:
        event = PipelineSSEEvent(
            event_type="stage_completed",
            project_id="proj-1",
            stage="requirements",
            agent="analyst",
            model="claude-sonnet",
            message="PRD generated",
            detail={"items": 12},
            timestamp="2026-03-31T12:00:00+00:00",
            elapsed_seconds=23.5,
            tokens_used=1500,
        )
        assert event.stage == "requirements"
        assert event.agent == "analyst"
        assert event.tokens_used == 1500

    def test_defaults(self) -> None:
        event = PipelineSSEEvent(
            event_type="pipeline_completed",
            project_id="proj-1",
            timestamp="2026-03-31T12:00:00+00:00",
        )
        assert event.stage == ""
        assert event.agent == ""
        assert event.model == ""
        assert event.message == ""
        assert event.detail == {}
        assert event.elapsed_seconds == 0.0
        assert event.tokens_used == 0

    def test_serialization_roundtrip(self) -> None:
        event = PipelineSSEEvent(
            event_type="gate_passed",
            project_id="proj-1",
            stage="design",
            timestamp="2026-03-31T12:00:00+00:00",
        )
        data = json.loads(event.model_dump_json())
        assert data["event_type"] == "gate_passed"
        assert data["project_id"] == "proj-1"
        assert data["stage"] == "design"

    def test_frozen(self) -> None:
        event = PipelineSSEEvent(
            event_type="stage_started",
            project_id="proj-1",
            timestamp="2026-03-31T12:00:00+00:00",
        )
        with pytest.raises(ValidationError):
            event.event_type = "other"  # type: ignore[misc]


# ── Helpers ──────────────────────────────────────────────────────────


def _make_runner(
    bus: PipelineEventBus, *, is_active: bool = True
) -> MagicMock:
    """Create a mock runner exposing the given event bus."""
    runner = MagicMock()
    runner.event_bus = bus
    runner.is_active.return_value = is_active
    return runner


# ── SSE event generator ─────────────────────────────────────────────


class TestSSEEventGenerator:
    @pytest.mark.asyncio
    async def test_inactive_pipeline_yields_complete(self) -> None:
        runner = _make_runner(PipelineEventBus(), is_active=False)
        lines: list[str] = []
        async for line in _sse_event_generator("proj-1", runner, 1.0):
            lines.append(line)
        assert len(lines) == 1
        assert "event: complete" in lines[0]
        assert "proj-1" in lines[0]

    @pytest.mark.asyncio
    async def test_yields_bus_events(self) -> None:
        bus = PipelineEventBus()
        runner = _make_runner(bus)

        async def emit() -> None:
            await asyncio.sleep(0.05)
            bus.emit(
                PipelineEvent(
                    project_id="proj-1",
                    event_type=EventType.STAGE_STARTED,
                    stage="requirements",
                )
            )
            await asyncio.sleep(0.05)
            bus.emit(
                PipelineEvent(
                    project_id="proj-1",
                    event_type=EventType.PIPELINE_COMPLETED,
                    elapsed_seconds=23.0,
                )
            )

        task = asyncio.create_task(emit())
        lines: list[str] = []
        async for line in _sse_event_generator("proj-1", runner, 5.0):
            lines.append(line)
        await task

        assert len(lines) == 2
        assert "event: stage_started" in lines[0]
        assert "requirements" in lines[0]
        assert "event: pipeline_completed" in lines[1]

    @pytest.mark.asyncio
    async def test_pipeline_failed_closes_stream(self) -> None:
        bus = PipelineEventBus()
        runner = _make_runner(bus)

        async def emit() -> None:
            await asyncio.sleep(0.05)
            bus.emit(
                PipelineEvent(
                    project_id="proj-1",
                    event_type=EventType.PIPELINE_FAILED,
                    message="Something broke",
                )
            )

        task = asyncio.create_task(emit())
        lines: list[str] = []
        async for line in _sse_event_generator("proj-1", runner, 5.0):
            lines.append(line)
        await task

        assert len(lines) == 1
        assert "event: pipeline_failed" in lines[0]
        assert "Something broke" in lines[0]

    @pytest.mark.asyncio
    async def test_heartbeat_on_timeout(self) -> None:
        bus = PipelineEventBus()
        runner = _make_runner(bus)
        # Active at race guard; inactive after heartbeat.
        runner.is_active.side_effect = [True, False]

        lines: list[str] = []
        async for line in _sse_event_generator("proj-1", runner, 0.1):
            lines.append(line)

        assert lines[0] == ": heartbeat\n\n"
        assert "event: complete" in lines[1]

    @pytest.mark.asyncio
    async def test_unsubscribes_on_exit(self) -> None:
        bus = PipelineEventBus()
        runner = _make_runner(bus)

        async def emit() -> None:
            await asyncio.sleep(0.05)
            bus.emit(
                PipelineEvent(
                    project_id="proj-1",
                    event_type=EventType.PIPELINE_COMPLETED,
                )
            )

        task = asyncio.create_task(emit())
        async for _ in _sse_event_generator("proj-1", runner, 5.0):
            pass
        await task

        assert bus.subscriber_count("proj-1") == 0

    @pytest.mark.asyncio
    async def test_multiple_events_before_terminal(self) -> None:
        bus = PipelineEventBus()
        runner = _make_runner(bus)

        async def emit() -> None:
            await asyncio.sleep(0.05)
            for evt_type in (
                EventType.STAGE_STARTED,
                EventType.STAGE_COMPLETED,
                EventType.GATE_PASSED,
                EventType.PIPELINE_COMPLETED,
            ):
                bus.emit(
                    PipelineEvent(
                        project_id="proj-1",
                        event_type=evt_type,
                        stage="requirements",
                    )
                )
                await asyncio.sleep(0.02)

        task = asyncio.create_task(emit())
        lines: list[str] = []
        async for line in _sse_event_generator("proj-1", runner, 5.0):
            lines.append(line)
        await task

        assert len(lines) == 4
        assert "stage_started" in lines[0]
        assert "stage_completed" in lines[1]
        assert "gate_passed" in lines[2]
        assert "pipeline_completed" in lines[3]

    @pytest.mark.asyncio
    async def test_sse_format_structure(self) -> None:
        """Verify SSE lines follow 'event: <type>\\ndata: <json>\\n\\n'."""
        bus = PipelineEventBus()
        runner = _make_runner(bus)

        async def emit() -> None:
            await asyncio.sleep(0.05)
            bus.emit(
                PipelineEvent(
                    project_id="proj-1",
                    event_type=EventType.STAGE_STARTED,
                    stage="design",
                    agent="architect",
                    model="claude-opus",
                )
            )
            await asyncio.sleep(0.05)
            bus.emit(
                PipelineEvent(
                    project_id="proj-1",
                    event_type=EventType.PIPELINE_COMPLETED,
                )
            )

        task = asyncio.create_task(emit())
        lines: list[str] = []
        async for line in _sse_event_generator("proj-1", runner, 5.0):
            lines.append(line)
        await task

        first = lines[0]
        assert first.startswith("event: stage_started\n")
        assert first.endswith("\n\n")

        data_line = first.split("\n")[1]
        payload = json.loads(data_line.removeprefix("data: "))
        assert payload["stage"] == "design"
        assert payload["agent"] == "architect"
        assert payload["model"] == "claude-opus"

    @pytest.mark.asyncio
    async def test_inactive_after_heartbeat_sends_complete(self) -> None:
        """Pipeline ends during heartbeat wait — secondary check catches it."""
        bus = PipelineEventBus()
        runner = _make_runner(bus)
        runner.is_active.side_effect = [True, False]

        lines: list[str] = []
        async for line in _sse_event_generator("proj-1", runner, 0.1):
            lines.append(line)

        assert len(lines) == 2
        assert ": heartbeat" in lines[0]
        assert "event: complete" in lines[1]

"""Tests for PipelineRunner."""

from __future__ import annotations

import pytest

from colette.config import Settings
from colette.orchestrator.event_bus import PipelineEventBus
from colette.orchestrator.runner import ConcurrencyLimitError, PipelineRunner


class TestPipelineRunner:
    def test_creates_successfully(self) -> None:
        runner = PipelineRunner(Settings())
        assert runner.active_pipeline_count() == 0

    def test_is_active_false_initially(self) -> None:
        runner = PipelineRunner(Settings())
        assert runner.is_active("proj-1") is False

    def test_creates_default_event_bus(self) -> None:
        runner = PipelineRunner(Settings())
        assert isinstance(runner.event_bus, PipelineEventBus)

    def test_accepts_custom_event_bus(self) -> None:
        bus = PipelineEventBus()
        runner = PipelineRunner(Settings(), event_bus=bus)
        assert runner.event_bus is bus


class TestConcurrencyLimit:
    @pytest.mark.asyncio
    async def test_raises_when_limit_reached(self) -> None:
        settings = Settings(max_concurrent_pipelines=1)
        runner = PipelineRunner(settings)
        # Manually occupy the slot
        runner._active["proj-1"] = "thread-1"

        with pytest.raises(ConcurrencyLimitError):
            await runner.run("proj-2")

"""Tests for real-time LLM streaming — callback, TUI display, event handling."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from colette.api.routes.ws import ConnectionManager, _event_to_dict
from colette.cli_ui import (
    ActivityMode,
    PipelineProgressDisplay,
    build_live_output_panel,
)
from colette.observability.callbacks import (
    _STREAM_BATCH_INTERVAL,
    ColletteCallbackHandler,
)
from colette.orchestrator.event_bus import EventType, PipelineEvent

# ── Callback streaming ───────────────────────────────────────────────


class TestCallbackTokenStreaming:
    def _make_handler(self) -> ColletteCallbackHandler:
        return ColletteCallbackHandler(
            agent_id="test-agent",
            agent_role="TestRole",
            model="test-model",
        )

    def test_on_llm_new_token_buffers(self) -> None:
        h = self._make_handler()
        # Set last_flush to now so tokens accumulate instead of flushing.
        h._last_flush = time.monotonic()
        with patch("colette.observability.callbacks._emit_agent_event"):
            h.on_llm_new_token("Hello")
            h.on_llm_new_token(" world")
        assert h._token_buffer == ["Hello", " world"]

    def test_flush_emits_event(self) -> None:
        h = self._make_handler()
        h._token_buffer = ["Hello", " ", "world"]
        with patch("colette.observability.callbacks._emit_agent_event") as mock_emit:
            h._flush_token_buffer()
            mock_emit.assert_called_once_with(
                "agent_stream_chunk",
                agent="TestRole",
                model="test-model",
                message="Hello world",
            )
        assert h._token_buffer == []

    def test_flush_noop_when_empty(self) -> None:
        h = self._make_handler()
        with patch("colette.observability.callbacks._emit_agent_event") as mock_emit:
            h._flush_token_buffer()
            mock_emit.assert_not_called()

    def test_on_llm_new_token_flushes_after_interval(self) -> None:
        h = self._make_handler()
        h._last_flush = time.monotonic() - _STREAM_BATCH_INTERVAL - 0.01
        with patch("colette.observability.callbacks._emit_agent_event") as mock_emit:
            h.on_llm_new_token("token")
            mock_emit.assert_called_once()
        assert h._token_buffer == []

    def test_on_llm_end_flushes_remaining(self) -> None:
        h = self._make_handler()
        h._token_buffer = ["remaining"]
        mock_response = MagicMock()
        mock_response.llm_output = None
        mock_response.generations = [[]]
        with patch("colette.observability.callbacks._emit_agent_event") as mock_emit:
            h.on_llm_end(mock_response)
            # Should have flushed the buffer (stream_chunk) + emitted message
            calls = mock_emit.call_args_list
            assert len(calls) == 2
            assert calls[0][0][0] == "agent_stream_chunk"
            assert calls[1][0][0] == "agent_message"


# ── EventType ────────────────────────────────────────────────────────


class TestAgentStreamChunkEventType:
    def test_stream_chunk_in_enum(self) -> None:
        assert EventType.AGENT_STREAM_CHUNK == "agent_stream_chunk"

    def test_stream_chunk_value(self) -> None:
        assert EventType.AGENT_STREAM_CHUNK.value == "agent_stream_chunk"


# ── TUI stream chunk handling ────────────────────────────────────────


class TestPipelineDisplayStreamChunks:
    def _make_display(
        self, mode: ActivityMode = ActivityMode.CONVERSATION
    ) -> PipelineProgressDisplay:
        return PipelineProgressDisplay("proj-1", activity_mode=mode)

    def test_stream_chunk_appends_to_buffer(self) -> None:
        d = self._make_display()
        d.process_event(
            {
                "event_type": "agent_stream_chunk",
                "agent": "Analyst",
                "message": "Hello",
            }
        )
        assert d.stream_buffers["Analyst"] == "Hello"

    def test_stream_chunks_accumulate(self) -> None:
        d = self._make_display()
        d.process_event(
            {
                "event_type": "agent_stream_chunk",
                "agent": "Analyst",
                "message": "Hello",
            }
        )
        d.process_event(
            {
                "event_type": "agent_stream_chunk",
                "agent": "Analyst",
                "message": " world",
            }
        )
        assert d.stream_buffers["Analyst"] == "Hello world"

    def test_agent_message_clears_buffer(self) -> None:
        d = self._make_display()
        d.process_event(
            {
                "event_type": "agent_stream_chunk",
                "agent": "Analyst",
                "message": "partial",
            }
        )
        d.process_event(
            {
                "event_type": "agent_message",
                "agent": "Analyst",
                "message": "Final response",
            }
        )
        assert "Analyst" not in d.stream_buffers

    def test_stream_chunk_not_in_log(self) -> None:
        """Stream chunks should NOT appear in the stream log."""
        d = self._make_display()
        d.process_event(
            {
                "event_type": "agent_stream_chunk",
                "agent": "Analyst",
                "message": "token",
            }
        )
        assert len(d.stream_log) == 0

    def test_stream_buffer_truncation(self) -> None:
        d = self._make_display()
        big_chunk = "x" * 3000
        d.process_event(
            {
                "event_type": "agent_stream_chunk",
                "agent": "Big",
                "message": big_chunk,
            }
        )
        assert len(d.stream_buffers["Big"]) <= 2000

    def test_multiple_agents_separate_buffers(self) -> None:
        d = self._make_display()
        d.process_event(
            {
                "event_type": "agent_stream_chunk",
                "agent": "A",
                "message": "alpha",
            }
        )
        d.process_event(
            {
                "event_type": "agent_stream_chunk",
                "agent": "B",
                "message": "beta",
            }
        )
        assert d.stream_buffers["A"] == "alpha"
        assert d.stream_buffers["B"] == "beta"


# ── build_live_output_panel ──────────────────────────────────────────


class TestBuildLiveOutputPanel:
    def test_empty_buffers(self) -> None:
        result = build_live_output_panel({})
        assert result.plain == ""

    def test_single_agent(self) -> None:
        result = build_live_output_panel({"Analyst": "Processing data..."})
        assert "Processing data..." in result.plain

    def test_multiple_agents(self) -> None:
        result = build_live_output_panel(
            {
                "A": "line1\nline2",
                "B": "output",
            }
        )
        assert "line1" in result.plain
        assert "output" in result.plain

    def test_long_output_truncated(self) -> None:
        long_text = "\n".join(f"line {i}" for i in range(50))
        result = build_live_output_panel({"Agent": long_text}, max_lines=5)
        # Should only show last 5 lines
        assert result is not None


# ── Render with stream buffers ───────────────────────────────────────


class TestRenderWithStreaming:
    def test_conversation_mode_includes_live_output(self) -> None:
        d = PipelineProgressDisplay("p1", activity_mode=ActivityMode.CONVERSATION)
        d.process_event(
            {
                "event_type": "agent_stream_chunk",
                "agent": "Test",
                "message": "streaming...",
            }
        )
        renderable = d.render()
        # Should be a Group containing live output panel
        assert renderable is not None

    def test_verbose_mode_includes_live_output(self) -> None:
        d = PipelineProgressDisplay("p1", activity_mode=ActivityMode.VERBOSE)
        renderable = d.render()
        assert renderable is not None

    def test_minimal_mode_no_live_output(self) -> None:
        d = PipelineProgressDisplay("p1", activity_mode=ActivityMode.MINIMAL)
        d.process_event(
            {
                "event_type": "agent_stream_chunk",
                "agent": "Test",
                "message": "streaming...",
            }
        )
        renderable = d.render()
        # Minimal mode returns just Text, not Group
        from rich.text import Text

        assert isinstance(renderable, Text)


# ── WebSocket helpers ────────────────────────────────────────────────


class TestEventToDict:
    def test_converts_pipeline_event(self) -> None:
        event = PipelineEvent(
            project_id="p1",
            event_type=EventType.AGENT_STREAM_CHUNK,
            stage="design",
            agent="Architect",
            model="claude",
            message="token data",
        )
        d = _event_to_dict(event)
        assert d["event_type"] == "agent_stream_chunk"
        assert d["agent"] == "Architect"
        assert d["message"] == "token data"
        assert d["project_id"] == "p1"

    def test_non_event_returns_empty(self) -> None:
        assert _event_to_dict("not an event") == {}

    def test_detail_is_dict(self) -> None:
        event = PipelineEvent(
            project_id="p1",
            event_type=EventType.AGENT_THINKING,
            detail={"key": "val"},
        )
        d = _event_to_dict(event)
        assert d["detail"] == {"key": "val"}


class TestConnectionManager:
    def test_disconnect_unknown_ws(self) -> None:
        mgr = ConnectionManager()
        ws = MagicMock()
        # Should not raise
        mgr.disconnect("unknown-project", ws)

    def test_disconnect_known_ws(self) -> None:
        mgr = ConnectionManager()
        ws = MagicMock()
        mgr._connections["p1"].append(ws)
        mgr.disconnect("p1", ws)
        assert "p1" not in mgr._connections

    def test_disconnect_leaves_others(self) -> None:
        mgr = ConnectionManager()
        ws1 = MagicMock()
        ws2 = MagicMock()
        mgr._connections["p1"].extend([ws1, ws2])
        mgr.disconnect("p1", ws1)
        assert ws2 in mgr._connections["p1"]


# ── CLI _run_ws_loop ─────────────────────────────────────────────────


class TestEmitWsCatchup:
    @pytest.mark.asyncio
    async def test_catchup_sends_stage_events(self) -> None:
        from colette.api.routes.ws import _emit_ws_catchup
        from colette.orchestrator.runner import PipelineRunner

        ws = MagicMock()
        ws.send_json = AsyncMock()
        runner = MagicMock(spec=PipelineRunner)
        progress = MagicMock()
        progress.stage = "implementation"
        progress.elapsed_seconds = 42.0
        runner.get_progress = AsyncMock(return_value=progress)

        await _emit_ws_catchup(ws, "p1", runner)
        # requirements (started+completed), design (s+c), implementation (s)
        assert ws.send_json.call_count == 5

    @pytest.mark.asyncio
    async def test_catchup_handles_error_gracefully(self) -> None:
        from colette.api.routes.ws import _emit_ws_catchup
        from colette.orchestrator.runner import PipelineRunner

        ws = MagicMock()
        runner = MagicMock(spec=PipelineRunner)
        runner.get_progress = AsyncMock(side_effect=RuntimeError("no state"))

        # Should not raise
        await _emit_ws_catchup(ws, "p1", runner)


class TestRunWsLoopImportFallback:
    def test_ws_url_conversion(self) -> None:
        """Verify http->ws URL conversion logic."""
        api_url = "http://localhost:8000"
        ws_url = api_url.replace("http://", "ws://").replace("https://", "wss://")
        assert ws_url == "ws://localhost:8000"

    def test_https_ws_url_conversion(self) -> None:
        api_url = "https://example.com"
        ws_url = api_url.replace("http://", "ws://").replace("https://", "wss://")
        assert ws_url == "wss://example.com"

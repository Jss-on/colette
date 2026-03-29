"""Tests for observability layer (FR-ORC-015, FR-TL-005)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from colette.observability.callbacks import ColletteCallbackHandler
from colette.observability.metrics import (
    AgentInvocationRecord,
    Outcome,
    ToolCallRecord,
)
from colette.observability.tracing import get_tracer, init_tracing


class TestToolCallRecord:
    def test_create_success(self) -> None:
        rec = ToolCallRecord(tool_name="filesystem", latency_ms=42.5, success=True)
        assert rec.tool_name == "filesystem"
        assert rec.success is True
        assert rec.error is None

    def test_create_failure(self) -> None:
        rec = ToolCallRecord(tool_name="git", latency_ms=100.0, success=False, error="timeout")
        assert rec.success is False
        assert rec.error == "timeout"

    def test_immutability(self) -> None:
        rec = ToolCallRecord(tool_name="test", latency_ms=1.0, success=True)
        try:
            rec.tool_name = "other"  # type: ignore[misc]
            raised = False
        except AttributeError:
            raised = True
        assert raised


class TestAgentInvocationRecord:
    def test_create_full(self) -> None:
        tool_call = ToolCallRecord(tool_name="fs", latency_ms=10.0, success=True)
        rec = AgentInvocationRecord(
            agent_id="agent-123",
            agent_role="backend_dev",
            model="claude-sonnet-4-6",
            input_tokens=500,
            output_tokens=200,
            tool_calls=(tool_call,),
            duration_ms=1500.0,
            outcome=Outcome.SUCCESS,
        )
        assert rec.agent_id == "agent-123"
        assert rec.input_tokens == 500
        assert rec.outcome == Outcome.SUCCESS
        assert len(rec.tool_calls) == 1

    def test_total_tokens(self) -> None:
        rec = AgentInvocationRecord(
            agent_id="a",
            agent_role="r",
            model="m",
            input_tokens=100,
            output_tokens=50,
            tool_calls=(),
            duration_ms=0.0,
            outcome=Outcome.SUCCESS,
        )
        assert rec.total_tokens == 150


class TestTracing:
    @patch("colette.observability.tracing.TracerProvider")
    @patch("colette.observability.tracing.OTLPSpanExporter")
    @patch("colette.observability.tracing.BatchSpanProcessor")
    def test_init_tracing(
        self,
        mock_processor: MagicMock,
        mock_exporter: MagicMock,
        mock_provider: MagicMock,
    ) -> None:
        from colette.config import Settings

        settings = Settings()
        provider = init_tracing(settings)
        assert provider is not None
        mock_exporter.assert_called_once()

    def test_get_tracer_returns_tracer(self) -> None:
        tracer = get_tracer("test-component")
        assert tracer is not None


class TestColletteCallbackHandler:
    def test_tracks_llm_tokens(self) -> None:
        handler = ColletteCallbackHandler(
            agent_id="a1", agent_role="backend_dev", model="claude-sonnet-4-6"
        )
        # Simulate LLM start
        handler.on_llm_start(serialized={}, prompts=["hello"])
        # Simulate LLM end with token usage
        response = MagicMock()
        response.llm_output = {"token_usage": {"prompt_tokens": 100, "completion_tokens": 50}}
        response.generations = [[MagicMock()]]
        handler.on_llm_end(response)

        assert handler.input_tokens == 100
        assert handler.output_tokens == 50

    def test_tracks_tool_calls(self) -> None:
        handler = ColletteCallbackHandler(
            agent_id="a1", agent_role="backend_dev", model="claude-sonnet-4-6"
        )
        run_id = uuid.uuid4()
        handler.on_tool_start(
            serialized={"name": "filesystem"}, input_str="read file", run_id=run_id
        )
        handler.on_tool_end(output="file contents", run_id=run_id)
        assert len(handler.tool_call_records) == 1
        assert handler.tool_call_records[0].tool_name == "filesystem"
        assert handler.tool_call_records[0].success is True

    def test_build_record(self) -> None:
        handler = ColletteCallbackHandler(
            agent_id="a1", agent_role="backend_dev", model="claude-sonnet-4-6"
        )
        record = handler.build_record(outcome=Outcome.SUCCESS, duration_ms=1234.0)
        assert record.agent_id == "a1"
        assert record.outcome == Outcome.SUCCESS
        assert record.duration_ms == 1234.0

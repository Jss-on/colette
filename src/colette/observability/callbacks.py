"""LangChain callback handler for agent observability (FR-ORC-015, FR-TL-005).

Attach an instance of ``ColletteCallbackHandler`` to every agent invocation
to automatically capture token counts, tool call metrics, and timing.
"""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

import structlog
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from colette.observability.metrics import AgentInvocationRecord, Outcome, ToolCallRecord

logger = structlog.get_logger(__name__)


class ColletteCallbackHandler(BaseCallbackHandler):
    """Tracks LLM tokens and tool calls for a single agent invocation."""

    def __init__(self, agent_id: str, agent_role: str, model: str) -> None:
        super().__init__()
        self.agent_id = agent_id
        self.agent_role = agent_role
        self.model = model

        # Token accumulators
        self.input_tokens: int = 0
        self.output_tokens: int = 0

        # Tool call tracking
        self.tool_call_records: list[ToolCallRecord] = []
        self._tool_start_times: dict[UUID, tuple[str, float]] = {}

    # ── LLM callbacks ───────────────────────────────────────────────

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        **kwargs: Any,
    ) -> None:
        pass  # Nothing to record until completion

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        if response.llm_output and "token_usage" in response.llm_output:
            usage = response.llm_output["token_usage"]
            self.input_tokens += usage.get("prompt_tokens", 0)
            self.output_tokens += usage.get("completion_tokens", 0)

    # ── Tool callbacks ──────────────────────────────────────────────

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        tool_name = serialized.get("name", "unknown")
        self._tool_start_times[run_id] = (tool_name, time.monotonic())

    def on_tool_end(self, output: str, *, run_id: UUID, **kwargs: Any) -> None:
        if run_id in self._tool_start_times:
            tool_name, start = self._tool_start_times.pop(run_id)
            latency_ms = (time.monotonic() - start) * 1000
            self.tool_call_records.append(
                ToolCallRecord(
                    tool_name=tool_name, latency_ms=latency_ms, success=True
                )
            )

    def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        if run_id in self._tool_start_times:
            tool_name, start = self._tool_start_times.pop(run_id)
            latency_ms = (time.monotonic() - start) * 1000
            self.tool_call_records.append(
                ToolCallRecord(
                    tool_name=tool_name,
                    latency_ms=latency_ms,
                    success=False,
                    error=str(error),
                )
            )

    # ── Record builder ──────────────────────────────────────────────

    def build_record(
        self, *, outcome: Outcome, duration_ms: float
    ) -> AgentInvocationRecord:
        """Build an immutable invocation record from accumulated data."""
        return AgentInvocationRecord(
            agent_id=self.agent_id,
            agent_role=self.agent_role,
            model=self.model,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            tool_calls=tuple(self.tool_call_records),
            duration_ms=duration_ms,
            outcome=outcome,
        )

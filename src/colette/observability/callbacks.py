"""LangChain callback handler for agent observability (FR-ORC-015, FR-TL-005).

Attach an instance of ``ColletteCallbackHandler`` to every agent invocation
to automatically capture token counts, tool call metrics, and timing.
Also emits agent-level events to the :class:`PipelineEventBus` via
async-safe context variables (Phase 7).
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


def _emit_agent_event(
    event_type: str,
    *,
    agent: str = "",
    model: str = "",
    message: str = "",
    detail: dict[str, Any] | None = None,
    tokens_used: int = 0,
) -> None:
    """Emit an agent-level event to the bus (if active in this context).

    Imports are deferred to avoid a circular dependency with
    ``colette.orchestrator``.
    """
    from colette.orchestrator.event_bus import (
        EventType,
        PipelineEvent,
        event_bus_var,
        project_id_var,
        stage_var,
    )

    bus = event_bus_var.get()
    if bus is None:
        return
    bus.emit(
        PipelineEvent(
            project_id=project_id_var.get(),
            event_type=EventType(event_type),
            stage=stage_var.get(),
            agent=agent,
            model=model,
            message=message,
            detail=detail or {},
            tokens_used=tokens_used,
        )
    )


class ColletteCallbackHandler(BaseCallbackHandler):
    """Tracks LLM tokens and tool calls for a single agent invocation.

    Attach one instance per :func:`invoke_agent` call.  After the agent
    finishes, call :meth:`build_record` to produce an immutable
    :class:`AgentInvocationRecord`.

    When pipeline context variables are set (see :mod:`event_bus`),
    callbacks also emit agent-level events to the SSE stream.

    Attributes:
        agent_id: Unique identifier of the agent invocation.
        agent_role: Role name (e.g. ``"backend_dev"``).
        model: Model tier or name used for this invocation.
        input_tokens: Accumulated prompt tokens across all LLM calls.
        output_tokens: Accumulated completion tokens across all LLM calls.
        tool_call_records: Completed tool call metrics.
    """

    def __init__(self, agent_id: str, agent_role: str, model: str) -> None:
        super().__init__()
        self.agent_id = agent_id
        self.agent_role = agent_role
        self.model = model

        self.input_tokens: int = 0
        self.output_tokens: int = 0

        self.tool_call_records: list[ToolCallRecord] = []
        self._tool_start_times: dict[UUID, tuple[str, float]] = {}

    # ── LLM callbacks ───────────────────────────────────────────────

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        **kwargs: Any,
    ) -> None:
        """Called when an LLM call begins.  Emits AGENT_THINKING."""
        logger.debug("llm_call_started", agent_id=self.agent_id)
        _emit_agent_event(
            "agent_thinking",
            agent=self.agent_role,
            model=self.model,
            message="Thinking...",
        )

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Called when an LLM call completes.  Extracts token usage, emits AGENT_MESSAGE."""
        tokens = 0
        if response.llm_output and "token_usage" in response.llm_output:
            usage = response.llm_output["token_usage"]
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            self.input_tokens += prompt_tokens
            self.output_tokens += completion_tokens
            tokens = prompt_tokens + completion_tokens
            logger.debug(
                "llm_call_completed",
                agent_id=self.agent_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
        _emit_agent_event(
            "agent_message",
            agent=self.agent_role,
            model=self.model,
            message="Response received",
            tokens_used=tokens,
        )

    # ── Tool callbacks ──────────────────────────────────────────────

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Called when a tool invocation begins.  Emits AGENT_TOOL_CALL."""
        tool_name = serialized.get("name", "unknown")
        self._tool_start_times[run_id] = (tool_name, time.monotonic())
        logger.debug("tool_started", agent_id=self.agent_id, tool_name=tool_name)
        _emit_agent_event(
            "agent_tool_call",
            agent=self.agent_role,
            message=f"Using tool: {tool_name}",
            detail={"tool": tool_name},
        )

    def on_tool_end(self, output: str, *, run_id: UUID, **kwargs: Any) -> None:
        """Called when a tool invocation succeeds.  Records latency."""
        if run_id in self._tool_start_times:
            tool_name, start = self._tool_start_times.pop(run_id)
            latency_ms = (time.monotonic() - start) * 1000
            self.tool_call_records.append(
                ToolCallRecord(tool_name=tool_name, latency_ms=latency_ms, success=True)
            )
            logger.debug(
                "tool_completed",
                agent_id=self.agent_id,
                tool_name=tool_name,
                latency_ms=round(latency_ms, 2),
            )

    def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        """Called when a tool invocation fails.  Records the error."""
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
            logger.warning(
                "tool_failed",
                agent_id=self.agent_id,
                tool_name=tool_name,
                error=str(error),
                latency_ms=round(latency_ms, 2),
            )

    # ── Record builder ──────────────────────────────────────────────

    def build_record(self, *, outcome: Outcome, duration_ms: float) -> AgentInvocationRecord:
        """Build an immutable invocation record from accumulated data.

        Args:
            outcome: Final outcome of the agent invocation.
            duration_ms: Total wall-clock time in milliseconds.

        Returns:
            An :class:`AgentInvocationRecord` snapshot.
        """
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

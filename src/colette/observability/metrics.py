"""Observability data models for agent and tool invocations (FR-ORC-015, FR-TL-005)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Outcome(StrEnum):
    """Agent invocation outcome."""

    SUCCESS = "success"
    FAILURE = "failure"
    ESCALATED = "escalated"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class ToolCallRecord:
    """Immutable record of a single tool invocation (FR-TL-005)."""

    tool_name: str
    latency_ms: float
    success: bool
    error: str | None = None


@dataclass(frozen=True)
class AgentInvocationRecord:
    """Immutable record of a complete agent invocation (FR-ORC-015).

    Contains: agent_id, model, token counts, tool calls, duration, outcome.
    """

    agent_id: str
    agent_role: str
    model: str
    input_tokens: int
    output_tokens: int
    tool_calls: tuple[ToolCallRecord, ...]
    duration_ms: float
    outcome: Outcome

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

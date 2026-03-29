"""Observability data models for agent and tool invocations (FR-ORC-015, FR-TL-005).

These frozen dataclasses are the canonical metric records emitted by
:class:`ColletteCallbackHandler` and consumed by dashboards and alerts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Outcome(StrEnum):
    """Agent invocation outcome.

    Attributes:
        SUCCESS: Agent completed normally.
        FAILURE: Agent raised an unrecoverable exception.
        ESCALATED: Error recovery escalated beyond the agent.
        TIMEOUT: Agent exceeded its time budget.
    """

    SUCCESS = "success"
    FAILURE = "failure"
    ESCALATED = "escalated"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class ToolCallRecord:
    """Immutable record of a single tool invocation (FR-TL-005).

    Attributes:
        tool_name: Name of the tool that was called.
        latency_ms: Wall-clock time for the call in milliseconds.
        success: Whether the call completed without error.
        error: Error message if the call failed, else ``None``.
    """

    tool_name: str
    latency_ms: float
    success: bool
    error: str | None = None


@dataclass(frozen=True)
class AgentInvocationRecord:
    """Immutable record of a complete agent invocation (FR-ORC-015).

    Attributes:
        agent_id: Unique ID for this invocation (``{role}-{uuid}``).
        agent_role: The agent's role name.
        model: Model tier or name used.
        input_tokens: Total prompt tokens consumed.
        output_tokens: Total completion tokens generated.
        tool_calls: Tuple of individual tool call records.
        duration_ms: Total wall-clock duration in milliseconds.
        outcome: Final outcome of the invocation.
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
        """Sum of input and output tokens."""
        return self.input_tokens + self.output_tokens

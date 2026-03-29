"""Observability: tracing, metrics, and LangChain callbacks (FR-ORC-015)."""

from colette.observability.callbacks import ColletteCallbackHandler
from colette.observability.metrics import AgentInvocationRecord, Outcome, ToolCallRecord
from colette.observability.tracing import get_tracer, init_tracing

__all__ = [
    "AgentInvocationRecord",
    "ColletteCallbackHandler",
    "Outcome",
    "ToolCallRecord",
    "get_tracer",
    "init_tracing",
]

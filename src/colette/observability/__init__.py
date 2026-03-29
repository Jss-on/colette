"""Observability: structured logging, tracing, metrics, and LangChain callbacks.

This package provides the full observability stack for Colette agents:

- :func:`configure_logging` -- structlog configuration with JSON/console output.
- :func:`init_tracing` / :func:`get_tracer` -- OpenTelemetry distributed tracing.
- :class:`ColletteCallbackHandler` -- LangChain callback for token and tool metrics.
- :class:`AgentInvocationRecord` / :class:`ToolCallRecord` -- immutable metric records.
"""

from colette.observability.callbacks import ColletteCallbackHandler
from colette.observability.logging import configure_logging
from colette.observability.metrics import AgentInvocationRecord, Outcome, ToolCallRecord
from colette.observability.tracing import get_tracer, init_tracing

__all__ = [
    "AgentInvocationRecord",
    "ColletteCallbackHandler",
    "Outcome",
    "ToolCallRecord",
    "configure_logging",
    "get_tracer",
    "init_tracing",
]

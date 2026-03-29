"""Project Orchestrator — decomposes requests into pipeline stages (FR-ORC-001)."""

from colette.orchestrator.agent_factory import (
    AgentInstance,
    CircuitBreakerOpenError,
    create_agent,
    invoke_agent,
)
from colette.orchestrator.circuit_breaker import CircuitBreaker, CircuitState
from colette.orchestrator.error_recovery import (
    ErrorRecoveryPolicy,
    EscalationLevel,
    EscalationResult,
    execute_with_recovery,
)
from colette.orchestrator.pipeline import build_pipeline
from colette.orchestrator.progress import ProgressEvent, state_to_progress_event
from colette.orchestrator.runner import ConcurrencyLimitError, PipelineRunner
from colette.orchestrator.state import STAGE_ORDER, PipelineState, create_initial_state

__all__ = [
    "STAGE_ORDER",
    "AgentInstance",
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    "CircuitState",
    "ConcurrencyLimitError",
    "ErrorRecoveryPolicy",
    "EscalationLevel",
    "EscalationResult",
    "PipelineRunner",
    "PipelineState",
    "ProgressEvent",
    "build_pipeline",
    "create_agent",
    "create_initial_state",
    "execute_with_recovery",
    "invoke_agent",
    "state_to_progress_event",
]

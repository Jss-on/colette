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

__all__ = [
    "AgentInstance",
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    "CircuitState",
    "ErrorRecoveryPolicy",
    "EscalationLevel",
    "EscalationResult",
    "create_agent",
    "execute_with_recovery",
    "invoke_agent",
]

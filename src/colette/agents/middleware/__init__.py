"""Composable agent middleware architecture (Phase 7a)."""

from colette.agents.middleware.event_emission import EventEmissionMiddleware
from colette.agents.middleware.protocol import (
    AgentMiddleware,
    AgentRequest,
    AgentResponse,
    MiddlewareStack,
)
from colette.agents.middleware.todo_list import TodoListMiddleware
from colette.agents.middleware.token_budget import TokenBudgetMiddleware

__all__ = [
    "AgentMiddleware",
    "AgentRequest",
    "AgentResponse",
    "EventEmissionMiddleware",
    "MiddlewareStack",
    "TodoListMiddleware",
    "TokenBudgetMiddleware",
]

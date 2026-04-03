"""Middleware protocol and stack for composable agent pipelines (Phase 7a)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class AgentRequest:
    """Request passed through the middleware chain."""

    system_prompt: str
    user_content: str
    tools: list[Any] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResponse:
    """Response returned through the middleware chain."""

    content: Any = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    token_usage: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


# Type alias for the handler function.
Handler = Callable[[AgentRequest], Awaitable[AgentResponse]]


class AgentMiddleware(Protocol):
    """Protocol for composable agent middleware."""

    async def __call__(
        self,
        request: AgentRequest,
        next_handler: Handler,
    ) -> AgentResponse: ...


class MiddlewareStack:
    """Chains middleware in order around a base handler.

    Middleware is applied in the order given: the first middleware
    in the list is the outermost wrapper.
    """

    def __init__(
        self,
        middlewares: list[AgentMiddleware],
        base_handler: Handler,
    ) -> None:
        self._middlewares = list(middlewares)
        self._base_handler = base_handler

    async def __call__(self, request: AgentRequest) -> AgentResponse:
        """Execute the middleware chain."""
        handler = self._base_handler
        for mw in reversed(self._middlewares):
            handler = _wrap(mw, handler)
        return await handler(request)


def _wrap(middleware: AgentMiddleware, next_handler: Handler) -> Handler:
    """Create a closure that calls middleware with next_handler."""

    async def wrapped(request: AgentRequest) -> AgentResponse:
        return await middleware(request, next_handler)

    return wrapped

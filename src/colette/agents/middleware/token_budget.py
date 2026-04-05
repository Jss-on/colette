"""Token budget middleware — enforces per-agent token limits (Phase 7a)."""

from __future__ import annotations

import structlog

from colette.agents.middleware.protocol import AgentRequest, AgentResponse, Handler

logger = structlog.get_logger(__name__)


class TokenBudgetExceededError(Exception):
    """Raised when an agent exceeds its token budget."""


class TokenBudgetMiddleware:
    """Enforces per-agent token limits and tracks cumulative usage."""

    def __init__(self, max_tokens: int = 100_000) -> None:
        self._max_tokens = max_tokens
        self._total_used = 0

    @property
    def total_used(self) -> int:
        """Total tokens consumed so far."""
        return self._total_used

    @property
    def remaining(self) -> int:
        """Tokens remaining in the budget."""
        return max(0, self._max_tokens - self._total_used)

    async def __call__(
        self,
        request: AgentRequest,
        next_handler: Handler,
    ) -> AgentResponse:
        if self._total_used >= self._max_tokens:
            raise TokenBudgetExceededError(
                f"Token budget exhausted: {self._total_used}/{self._max_tokens}"
            )

        response = await next_handler(request)

        call_tokens = sum(response.token_usage.values())
        self._total_used += call_tokens

        if self._total_used >= self._max_tokens:
            logger.warning(
                "token_budget.exceeded",
                total_used=self._total_used,
                max_tokens=self._max_tokens,
            )

        return response

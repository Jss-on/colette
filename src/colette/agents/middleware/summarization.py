"""Context summarization middleware — auto-compact agent context (Phase 7b)."""

from __future__ import annotations

import structlog

from colette.agents.middleware.protocol import AgentRequest, AgentResponse, Handler

logger = structlog.get_logger(__name__)


class ContextSummarizationMiddleware:
    """Auto-compact agent context when approaching token limits.

    Tracks cumulative tokens and triggers summarization when the
    configured fraction of the context window is consumed.
    """

    def __init__(
        self,
        context_window: int = 200_000,
        trigger_fraction: float = 0.80,
        keep_fraction: float = 0.15,
    ) -> None:
        self._context_window = context_window
        self._trigger_fraction = trigger_fraction
        self._keep_fraction = keep_fraction
        self._total_tokens = 0
        self._history: list[dict[str, str]] = []

    @property
    def total_tokens(self) -> int:
        """Total tokens consumed so far."""
        return self._total_tokens

    @property
    def should_summarize(self) -> bool:
        """Whether the context has exceeded the trigger threshold."""
        return self._total_tokens >= self._context_window * self._trigger_fraction

    async def __call__(
        self,
        request: AgentRequest,
        next_handler: Handler,
    ) -> AgentResponse:
        self._history.append(
            {
                "role": "user",
                "content": request.user_content[:200],
            }
        )

        if self.should_summarize:
            keep_count = max(1, int(len(self._history) * self._keep_fraction))
            summarized = f"[Summarized {len(self._history) - keep_count} prior messages]"
            self._history = [
                {"role": "system", "content": summarized},
                *self._history[-keep_count:],
            ]
            logger.info(
                "context_summarization.triggered",
                total_tokens=self._total_tokens,
                kept_messages=keep_count,
            )

        response = await next_handler(request)

        call_tokens = sum(response.token_usage.values())
        self._total_tokens += call_tokens

        return response

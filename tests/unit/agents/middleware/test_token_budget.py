"""Tests for token budget middleware (Phase 7a)."""

from __future__ import annotations

import pytest

from colette.agents.middleware.protocol import AgentRequest, AgentResponse
from colette.agents.middleware.token_budget import (
    TokenBudgetExceededError,
    TokenBudgetMiddleware,
)


async def _handler_with_tokens(tokens: int):
    async def handler(request: AgentRequest) -> AgentResponse:
        return AgentResponse(token_usage={"total": tokens})

    return handler


class TestTokenBudgetMiddleware:
    @pytest.mark.asyncio
    async def test_tracks_usage(self) -> None:
        mw = TokenBudgetMiddleware(max_tokens=1000)
        handler = await _handler_with_tokens(100)
        req = AgentRequest(system_prompt="", user_content="")
        await mw(req, handler)
        assert mw.total_used == 100
        assert mw.remaining == 900

    @pytest.mark.asyncio
    async def test_accumulates_across_calls(self) -> None:
        mw = TokenBudgetMiddleware(max_tokens=500)
        handler = await _handler_with_tokens(200)
        req = AgentRequest(system_prompt="", user_content="")
        await mw(req, handler)
        await mw(req, handler)
        assert mw.total_used == 400

    @pytest.mark.asyncio
    async def test_raises_when_exhausted(self) -> None:
        mw = TokenBudgetMiddleware(max_tokens=100)
        handler = await _handler_with_tokens(150)
        req = AgentRequest(system_prompt="", user_content="")
        await mw(req, handler)  # 150 > 100, total_used = 150
        with pytest.raises(TokenBudgetExceededError):
            await mw(req, handler)  # budget already exhausted

    @pytest.mark.asyncio
    async def test_remaining_floors_at_zero(self) -> None:
        mw = TokenBudgetMiddleware(max_tokens=50)
        handler = await _handler_with_tokens(100)
        req = AgentRequest(system_prompt="", user_content="")
        await mw(req, handler)
        assert mw.remaining == 0

"""Tests for context summarization middleware (Phase 7b)."""

from __future__ import annotations

import pytest

from colette.agents.middleware.protocol import AgentRequest, AgentResponse
from colette.agents.middleware.summarization import ContextSummarizationMiddleware


async def _handler(request: AgentRequest) -> AgentResponse:
    return AgentResponse(token_usage={"total": 1000})


class TestContextSummarizationMiddleware:
    def test_initial_state(self) -> None:
        mw = ContextSummarizationMiddleware(context_window=10000)
        assert mw.total_tokens == 0
        assert mw.should_summarize is False

    @pytest.mark.asyncio
    async def test_tracks_tokens(self) -> None:
        mw = ContextSummarizationMiddleware(context_window=10000)
        req = AgentRequest(system_prompt="", user_content="hello")
        await mw(req, _handler)
        assert mw.total_tokens == 1000

    @pytest.mark.asyncio
    async def test_triggers_summarization(self) -> None:
        mw = ContextSummarizationMiddleware(context_window=1000, trigger_fraction=0.50)

        async def handler_600(r: AgentRequest) -> AgentResponse:
            return AgentResponse(token_usage={"total": 600})

        req = AgentRequest(system_prompt="", user_content="msg")
        await mw(req, handler_600)
        assert mw.should_summarize is True

    @pytest.mark.asyncio
    async def test_keeps_recent_messages(self) -> None:
        mw = ContextSummarizationMiddleware(
            context_window=100, trigger_fraction=0.01, keep_fraction=0.50
        )
        req = AgentRequest(system_prompt="", user_content="msg")
        for _ in range(5):
            await mw(req, _handler)
        # History should be compacted
        assert len(mw._history) <= 5

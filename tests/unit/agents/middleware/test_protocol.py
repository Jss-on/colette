"""Tests for middleware protocol and stack (Phase 7a)."""

from __future__ import annotations

import pytest

from colette.agents.middleware.protocol import (
    AgentRequest,
    AgentResponse,
    MiddlewareStack,
)


async def _echo_handler(request: AgentRequest) -> AgentResponse:
    return AgentResponse(content=request.user_content, metadata={"echoed": True})


class TestAgentRequest:
    def test_defaults(self) -> None:
        req = AgentRequest(system_prompt="sys", user_content="user")
        assert req.tools == []
        assert req.state == {}
        assert req.metadata == {}


class TestAgentResponse:
    def test_defaults(self) -> None:
        resp = AgentResponse()
        assert resp.content is None
        assert resp.tool_calls == []
        assert resp.token_usage == {}


class TestMiddlewareStack:
    @pytest.mark.asyncio
    async def test_no_middleware(self) -> None:
        stack = MiddlewareStack([], _echo_handler)
        req = AgentRequest(system_prompt="", user_content="hello")
        resp = await stack(req)
        assert resp.content == "hello"

    @pytest.mark.asyncio
    async def test_single_middleware(self) -> None:
        async def add_tag(req: AgentRequest, next_h):
            req.metadata["tagged"] = True
            return await next_h(req)

        stack = MiddlewareStack([add_tag], _echo_handler)
        req = AgentRequest(system_prompt="", user_content="hi")
        resp = await stack(req)
        assert resp.content == "hi"

    @pytest.mark.asyncio
    async def test_middleware_order(self) -> None:
        order: list[str] = []

        async def mw_a(req: AgentRequest, next_h):
            order.append("a_before")
            resp = await next_h(req)
            order.append("a_after")
            return resp

        async def mw_b(req: AgentRequest, next_h):
            order.append("b_before")
            resp = await next_h(req)
            order.append("b_after")
            return resp

        stack = MiddlewareStack([mw_a, mw_b], _echo_handler)
        await stack(AgentRequest(system_prompt="", user_content=""))
        assert order == ["a_before", "b_before", "b_after", "a_after"]

    @pytest.mark.asyncio
    async def test_middleware_can_modify_response(self) -> None:
        async def add_tokens(req: AgentRequest, next_h):
            resp = await next_h(req)
            resp.token_usage = {"total": 100}
            return resp

        stack = MiddlewareStack([add_tokens], _echo_handler)
        resp = await stack(AgentRequest(system_prompt="", user_content=""))
        assert resp.token_usage == {"total": 100}

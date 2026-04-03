"""Tests for subagent isolation (Phase 7c)."""

from __future__ import annotations

import pytest

from colette.agents.middleware.protocol import AgentRequest, AgentResponse
from colette.agents.subagent import SubAgentSpec, spawn_subagent


@pytest.mark.asyncio
async def test_spawn_subagent_default_handler() -> None:
    spec = SubAgentSpec(
        name="test_agent",
        description="A test agent",
        system_prompt="You are a test agent.",
    )
    response = await spawn_subagent(spec, {"user_content": "hello"})
    assert "test_agent" in response.content
    assert response.metadata["agent"] == "test_agent"


@pytest.mark.asyncio
async def test_spawn_subagent_custom_handler() -> None:
    async def custom(request: AgentRequest) -> AgentResponse:
        return AgentResponse(content=f"custom: {request.user_content}")

    spec = SubAgentSpec(name="custom", description="", system_prompt="")
    response = await spawn_subagent(spec, {"user_content": "hi"}, handler=custom)
    assert response.content == "custom: hi"


@pytest.mark.asyncio
async def test_spawn_subagent_with_middleware() -> None:
    calls: list[str] = []

    async def tracking_mw(req: AgentRequest, next_h):
        calls.append("before")
        resp = await next_h(req)
        calls.append("after")
        return resp

    spec = SubAgentSpec(
        name="mw_agent",
        description="",
        system_prompt="",
        middleware=[tracking_mw],
    )
    await spawn_subagent(spec, {})
    assert calls == ["before", "after"]


def test_subagent_spec_defaults() -> None:
    spec = SubAgentSpec(name="a", description="b", system_prompt="c")
    assert spec.tools == []
    assert spec.model == ""
    assert spec.middleware == []

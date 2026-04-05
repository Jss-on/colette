"""Tests for event emission middleware (Phase 7a)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from colette.agents.middleware.event_emission import EventEmissionMiddleware
from colette.agents.middleware.protocol import AgentRequest, AgentResponse
from colette.orchestrator.event_bus import EventType, event_bus_var


async def _noop_handler(request: AgentRequest) -> AgentResponse:
    return AgentResponse(token_usage={"total": 50})


class TestEventEmissionMiddleware:
    @pytest.mark.asyncio
    async def test_emits_thinking_and_completed(self) -> None:
        bus = MagicMock()
        token = event_bus_var.set(bus)
        try:
            mw = EventEmissionMiddleware(agent_name="test_agent")
            req = AgentRequest(system_prompt="", user_content="")
            await mw(req, _noop_handler)
            assert bus.emit.call_count == 2
            events = [c.args[0] for c in bus.emit.call_args_list]
            assert events[0].event_type == EventType.AGENT_THINKING
            assert events[1].event_type == EventType.AGENT_COMPLETED
        finally:
            event_bus_var.reset(token)

    @pytest.mark.asyncio
    async def test_no_bus_no_error(self) -> None:
        mw = EventEmissionMiddleware(agent_name="test")
        req = AgentRequest(system_prompt="", user_content="")
        resp = await mw(req, _noop_handler)
        assert resp.token_usage == {"total": 50}

    @pytest.mark.asyncio
    async def test_uses_metadata_agent_name(self) -> None:
        bus = MagicMock()
        token = event_bus_var.set(bus)
        try:
            mw = EventEmissionMiddleware()
            req = AgentRequest(
                system_prompt="",
                user_content="",
                metadata={"agent_name": "from_meta"},
            )
            await mw(req, _noop_handler)
            event = bus.emit.call_args_list[0].args[0]
            assert event.agent == "from_meta"
        finally:
            event_bus_var.reset(token)

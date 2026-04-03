"""Tests for human-in-the-loop middleware (Phase 7g)."""

from __future__ import annotations

import pytest

from colette.agents.middleware.human_in_the_loop import (
    HumanInTheLoopMiddleware,
    InterruptOnConfig,
)
from colette.agents.middleware.protocol import AgentRequest, AgentResponse


async def _handler_with_calls(request: AgentRequest) -> AgentResponse:
    return AgentResponse(
        tool_calls=[
            {"name": "write_file", "args": {"path": "src/main.py"}},
            {"name": "execute_shell", "args": {"cmd": "rm -rf /"}},
        ]
    )


async def _handler_no_calls(request: AgentRequest) -> AgentResponse:
    return AgentResponse()


class TestHumanInTheLoopMiddleware:
    def test_no_interrupts_configured(self) -> None:
        mw = HumanInTheLoopMiddleware()
        assert mw.should_interrupt("write_file", {}) is False

    def test_bool_interrupt(self) -> None:
        mw = HumanInTheLoopMiddleware(interrupt_on={"execute_shell": True})
        assert mw.should_interrupt("execute_shell", {}) is True

    def test_config_interrupt_with_pattern(self) -> None:
        config = InterruptOnConfig(path_patterns=["*/migrations/*"])
        mw = HumanInTheLoopMiddleware(interrupt_on={"write_file": config})
        assert mw.should_interrupt("write_file", {"path": "db/migrations/001.sql"}) is True
        assert mw.should_interrupt("write_file", {"path": "src/main.py"}) is False

    def test_disabled_config(self) -> None:
        config = InterruptOnConfig(enabled=False)
        mw = HumanInTheLoopMiddleware(interrupt_on={"write_file": config})
        assert mw.should_interrupt("write_file", {}) is False

    @pytest.mark.asyncio
    async def test_flags_interrupted_tools(self) -> None:
        mw = HumanInTheLoopMiddleware(interrupt_on={"execute_shell": True})
        req = AgentRequest(system_prompt="", user_content="")
        resp = await mw(req, _handler_with_calls)
        assert len(mw.pending_approvals) == 1
        assert mw.pending_approvals[0]["tool_name"] == "execute_shell"
        assert "interrupted_tools" in resp.metadata

    @pytest.mark.asyncio
    async def test_no_flags_when_no_matches(self) -> None:
        mw = HumanInTheLoopMiddleware(interrupt_on={"delete_db": True})
        req = AgentRequest(system_prompt="", user_content="")
        resp = await mw(req, _handler_with_calls)
        assert len(mw.pending_approvals) == 0
        assert "interrupted_tools" not in resp.metadata

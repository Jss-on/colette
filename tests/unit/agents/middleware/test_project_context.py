"""Tests for project context middleware (Phase 7f)."""

from __future__ import annotations

import pytest

from colette.agents.middleware.project_context import ProjectContextMiddleware
from colette.agents.middleware.protocol import AgentRequest, AgentResponse


async def _echo(request: AgentRequest) -> AgentResponse:
    return AgentResponse(metadata={"prompt": request.system_prompt})


class TestProjectContextMiddleware:
    def test_load_memory(self) -> None:
        mw = ProjectContextMiddleware()
        mw.load_memory("project", "Project conventions...")
        assert mw.memory_count == 1

    @pytest.mark.asyncio
    async def test_injects_context(self) -> None:
        mw = ProjectContextMiddleware()
        mw.load_memory("project", "Use REST APIs")
        req = AgentRequest(system_prompt="Base", user_content="")
        resp = await mw(req, _echo)
        assert "Project Context" in resp.metadata["prompt"]
        assert "Use REST APIs" in resp.metadata["prompt"]

    @pytest.mark.asyncio
    async def test_no_memory_no_injection(self) -> None:
        mw = ProjectContextMiddleware()
        req = AgentRequest(system_prompt="Base", user_content="")
        resp = await mw(req, _echo)
        assert resp.metadata["prompt"] == "Base"

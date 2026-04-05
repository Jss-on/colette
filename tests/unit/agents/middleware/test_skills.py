"""Tests for skills middleware (Phase 7f)."""

from __future__ import annotations

import pytest

from colette.agents.middleware.protocol import AgentRequest, AgentResponse
from colette.agents.middleware.skills import AgentSkillsMiddleware


async def _echo(request: AgentRequest) -> AgentResponse:
    return AgentResponse(metadata={"prompt": request.system_prompt})


class TestAgentSkillsMiddleware:
    def test_register_skill(self) -> None:
        mw = AgentSkillsMiddleware()
        mw.register_skill("python", "Python patterns...")
        assert mw.skill_count == 1

    @pytest.mark.asyncio
    async def test_injects_skills_into_prompt(self) -> None:
        mw = AgentSkillsMiddleware()
        mw.register_skill("testing", "Testing best practices")
        req = AgentRequest(system_prompt="Base", user_content="")
        resp = await mw(req, _echo)
        assert "Loaded Skills" in resp.metadata["prompt"]
        assert "Testing best practices" in resp.metadata["prompt"]

    @pytest.mark.asyncio
    async def test_no_skills_no_injection(self) -> None:
        mw = AgentSkillsMiddleware()
        req = AgentRequest(system_prompt="Base", user_content="")
        resp = await mw(req, _echo)
        assert resp.metadata["prompt"] == "Base"

    @pytest.mark.asyncio
    async def test_tag_filtering(self) -> None:
        mw = AgentSkillsMiddleware()
        mw.register_skill("python", "Python skill")
        mw.register_skill("go", "Go skill")
        req = AgentRequest(
            system_prompt="Base",
            user_content="",
            metadata={"skill_tags": ["python"]},
        )
        resp = await mw(req, _echo)
        assert "Python skill" in resp.metadata["prompt"]
        assert "Go skill" not in resp.metadata["prompt"]

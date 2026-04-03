"""Skills middleware — loads dynamic agent capabilities from skill files (Phase 7f)."""

from __future__ import annotations

from colette.agents.middleware.protocol import AgentRequest, AgentResponse, Handler


class AgentSkillsMiddleware:
    """Loads SKILL.md files and injects relevant skills into agent prompts.

    Skills are matched by name or tag against the request metadata.
    """

    def __init__(self, skill_paths: list[str] | None = None) -> None:
        self._skill_paths = skill_paths or []
        self._loaded_skills: dict[str, str] = {}

    def register_skill(self, name: str, content: str) -> None:
        """Register a skill by name."""
        self._loaded_skills[name] = content

    @property
    def skill_count(self) -> int:
        """Number of registered skills."""
        return len(self._loaded_skills)

    async def __call__(
        self,
        request: AgentRequest,
        next_handler: Handler,
    ) -> AgentResponse:
        # Match skills based on metadata tags.
        tags = request.metadata.get("skill_tags", [])
        matched = [
            content for name, content in self._loaded_skills.items() if not tags or name in tags
        ]

        if matched:
            skills_section = "\n\n## Loaded Skills\n\n" + "\n---\n".join(matched)
            request.system_prompt += skills_section

        return await next_handler(request)

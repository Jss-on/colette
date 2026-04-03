"""Project context middleware — injects memory files into agent prompts (Phase 7f)."""

from __future__ import annotations

from colette.agents.middleware.protocol import AgentRequest, AgentResponse, Handler


class ProjectContextMiddleware:
    """Loads structured memory files and injects into agent system prompts.

    Memory content is always present — no retrieval step needed.
    """

    def __init__(self) -> None:
        self._memory_entries: dict[str, str] = {}

    def load_memory(self, key: str, content: str) -> None:
        """Load a memory entry by key (e.g. 'project', 'sprint_1')."""
        self._memory_entries[key] = content

    @property
    def memory_count(self) -> int:
        """Number of loaded memory entries."""
        return len(self._memory_entries)

    async def __call__(
        self,
        request: AgentRequest,
        next_handler: Handler,
    ) -> AgentResponse:
        if self._memory_entries:
            context_section = "\n\n## Project Context\n\n"
            for key, content in self._memory_entries.items():
                context_section += f"### {key}\n{content}\n\n"
            request.system_prompt += context_section

        return await next_handler(request)

"""Subagent isolation — specialist agents in isolated context windows (Phase 7c)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from colette.agents.middleware.protocol import (
    AgentMiddleware,
    AgentRequest,
    AgentResponse,
    MiddlewareStack,
)


@dataclass
class SubAgentSpec:
    """Specification for spawning an isolated subagent."""

    name: str
    description: str
    system_prompt: str
    tools: list[Any] = field(default_factory=list)
    model: str = ""
    middleware: list[AgentMiddleware] = field(default_factory=list)


async def spawn_subagent(
    spec: SubAgentSpec,
    context: dict[str, Any],
    *,
    handler: Any = None,
) -> AgentResponse:
    """Spawn a subagent with isolated context.

    The subagent runs with its own middleware stack and receives only
    the context explicitly passed to it, providing isolation from the
    parent agent's state.
    """

    async def _default_handler(request: AgentRequest) -> AgentResponse:
        return AgentResponse(
            content=f"[{spec.name}] processed request",
            metadata={"agent": spec.name},
        )

    base_handler = handler or _default_handler

    stack = MiddlewareStack(spec.middleware, base_handler)

    request = AgentRequest(
        system_prompt=spec.system_prompt,
        user_content=str(context.get("user_content", "")),
        tools=spec.tools,
        state=context,
        metadata={"agent_name": spec.name, "model": spec.model},
    )

    return await stack(request)

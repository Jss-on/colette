"""Event emission middleware — emits agent lifecycle events (Phase 7a)."""

from __future__ import annotations

from colette.agents.middleware.protocol import AgentRequest, AgentResponse, Handler
from colette.orchestrator.event_bus import (
    EventType,
    PipelineEvent,
    event_bus_var,
    project_id_var,
    stage_var,
)


class EventEmissionMiddleware:
    """Emits AGENT_THINKING and AGENT_COMPLETED events around agent calls."""

    def __init__(self, agent_name: str = "") -> None:
        self._agent_name = agent_name

    async def __call__(
        self,
        request: AgentRequest,
        next_handler: Handler,
    ) -> AgentResponse:
        bus = event_bus_var.get()
        agent = self._agent_name or request.metadata.get("agent_name", "unknown")

        if bus is not None:
            bus.emit(
                PipelineEvent(
                    project_id=project_id_var.get(""),
                    event_type=EventType.AGENT_THINKING,
                    stage=stage_var.get(""),
                    agent=agent,
                    message=f"Agent {agent} processing request",
                )
            )

        response = await next_handler(request)

        if bus is not None:
            tokens = sum(response.token_usage.values())
            bus.emit(
                PipelineEvent(
                    project_id=project_id_var.get(""),
                    event_type=EventType.AGENT_COMPLETED,
                    stage=stage_var.get(""),
                    agent=agent,
                    tokens_used=tokens,
                    message=f"Agent {agent} completed",
                )
            )

        return response

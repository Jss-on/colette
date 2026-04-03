"""Per-tool human-in-the-loop middleware (Phase 7g)."""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from colette.agents.middleware.protocol import AgentRequest, AgentResponse, Handler

logger = structlog.get_logger(__name__)


@dataclass
class InterruptOnConfig:
    """Configuration for conditional tool interrupts."""

    enabled: bool = True
    path_patterns: list[str] = field(default_factory=list)


class HumanInTheLoopMiddleware:
    """Fine-grained human approval at the tool level.

    Checks tool calls against interrupt rules and flags those
    requiring human approval before execution.
    """

    def __init__(
        self,
        interrupt_on: dict[str, bool | InterruptOnConfig] | None = None,
    ) -> None:
        self._interrupt_on = interrupt_on or {}
        self._pending_approvals: list[dict[str, object]] = []

    @property
    def pending_approvals(self) -> list[dict[str, object]]:
        """Tool calls awaiting human approval."""
        return list(self._pending_approvals)

    def should_interrupt(self, tool_name: str, args: dict[str, object]) -> bool:
        """Check if a tool call requires human approval."""
        config = self._interrupt_on.get(tool_name)
        if config is None:
            return False
        if isinstance(config, bool):
            return config
        if not config.enabled:
            return False
        if not config.path_patterns:
            return True
        # Check if any argument matches the path patterns.
        import fnmatch

        for pattern in config.path_patterns:
            for val in args.values():
                if isinstance(val, str) and fnmatch.fnmatch(val, pattern):
                    return True
        return False

    async def __call__(
        self,
        request: AgentRequest,
        next_handler: Handler,
    ) -> AgentResponse:
        response = await next_handler(request)

        # Check tool calls for interrupt triggers.
        flagged: list[dict[str, object]] = []
        for call in response.tool_calls:
            tool_name = call.get("name", "")
            tool_args = call.get("args", {})
            if self.should_interrupt(tool_name, tool_args):
                flagged.append(
                    {
                        "tool_name": tool_name,
                        "args": tool_args,
                        "requires_approval": True,
                    }
                )

        if flagged:
            self._pending_approvals.extend(flagged)
            response.metadata["interrupted_tools"] = flagged
            logger.info(
                "hil.tools_interrupted",
                count=len(flagged),
                tools=[f["tool_name"] for f in flagged],
            )

        return response

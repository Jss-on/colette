"""Tool registry with access control (FR-TL-003).

The registry holds all available tools and enforces per-agent access
lists.  Unauthorized access attempts are logged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from langchain_core.tools import BaseTool

if TYPE_CHECKING:
    from colette.schemas.agent_config import AgentConfig

logger = structlog.get_logger(__name__)


class ToolRegistry:
    """Manages tool registration and per-agent access control."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool by its name."""
        self._tools[tool.name] = tool

    def get_tools_for_agent(self, agent_config: AgentConfig) -> list[BaseTool]:
        """Return only tools the agent is authorized to use (FR-TL-003).

        Tools listed in ``agent_config.tool_names`` but not registered
        are logged as unauthorized access attempts.
        """
        tools: list[BaseTool] = []
        for name in agent_config.tool_names:
            tool = self._tools.get(name)
            if tool is not None:
                tools.append(tool)
            else:
                logger.warning(
                    "unauthorized_tool_access",
                    agent_role=agent_config.role,
                    tool_name=name,
                )
        return tools

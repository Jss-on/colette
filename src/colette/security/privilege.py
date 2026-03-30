"""Inter-agent privilege isolation (NFR-SEC-011).

Each agent is registered with an explicit set of allowed tools, an approval
tier ceiling, and an escalation flag.  The registry enforces that no agent
can access tools or tiers beyond its grant.
"""

from __future__ import annotations

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Approval tier ordering (lowest → highest privilege)
# ---------------------------------------------------------------------------

_TIER_ORDER: dict[str, int] = {
    "T3": 0,
    "T2": 1,
    "T1": 2,
    "T0": 3,
}

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class AgentPrivileges(BaseModel):
    """Declared privilege grant for a single agent."""

    model_config = {"frozen": True}

    agent_id: str = Field(description="Unique agent identifier.")
    role: str = Field(description="Functional role (e.g. 'frontend_dev').")
    allowed_tools: frozenset[str] = Field(
        default_factory=frozenset,
        description="Tools this agent may invoke.",
    )
    approval_tier_max: str = Field(
        description="Highest approval tier this agent may operate at (T0-T3).",
    )
    can_escalate: bool = Field(
        default=False,
        description="Whether the agent may request escalation to a higher tier.",
    )


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


class PrivilegeViolationError(PermissionError):
    """Raised when an agent attempts an action beyond its privilege grant."""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class PrivilegeRegistry:
    """Central registry of agent privilege grants.

    Agents must be registered before they can be checked.  Unregistered
    agents are denied by default.
    """

    def __init__(self) -> None:
        self._agents: dict[str, AgentPrivileges] = {}

    # -- registration ------------------------------------------------------

    def register(self, privileges: AgentPrivileges) -> None:
        """Register or overwrite a privilege grant for an agent."""
        self._agents[privileges.agent_id] = privileges
        logger.debug(
            "agent_privileges_registered",
            agent_id=privileges.agent_id,
            role=privileges.role,
        )

    # -- lookup ------------------------------------------------------------

    def get(self, agent_id: str) -> AgentPrivileges:
        """Return the privilege grant for *agent_id*.

        Raises ``PrivilegeViolationError`` if the agent is not registered.
        """
        priv = self._agents.get(agent_id)
        if priv is None:
            msg = f"Agent '{agent_id}' is not registered in the privilege registry."
            raise PrivilegeViolationError(msg)
        return priv

    # -- checks ------------------------------------------------------------

    def check_tool_access(self, agent_id: str, tool_name: str) -> bool:
        """Return ``True`` if *agent_id* is allowed to invoke *tool_name*."""
        try:
            priv = self.get(agent_id)
        except PrivilegeViolationError:
            return False
        return tool_name in priv.allowed_tools

    def check_escalation(self, requester_id: str, target_tier: str) -> bool:
        """Return whether *requester_id* may escalate to *target_tier*.

        Rules:
        - The agent must have ``can_escalate`` set to ``True``.
        - The *target_tier* must be at most one level above the agent's
          ``approval_tier_max`` (prevents self-escalation across multiple
          tiers).
        - If the target tier is at or below the agent's current tier the
          check passes trivially.
        """
        try:
            priv = self.get(requester_id)
        except PrivilegeViolationError:
            return False

        if not priv.can_escalate:
            return False

        current_level = _TIER_ORDER.get(priv.approval_tier_max)
        target_level = _TIER_ORDER.get(target_tier)

        if current_level is None or target_level is None:
            logger.warning(
                "unknown_tier",
                current=priv.approval_tier_max,
                target=target_tier,
            )
            return False

        # Already at or above the target — trivially allowed.
        if target_level <= current_level:
            return True

        # Allow escalation of at most one tier above current ceiling.
        return target_level - current_level <= 1

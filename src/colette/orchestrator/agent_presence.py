"""Agent presence tracking for Slack-style activity feed (Phase 7)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

__all__ = [
    "AgentPresence",
    "AgentPresenceTracker",
    "AgentState",
    "ConversationEntry",
]

DEFAULT_MAX_CONVERSATION = 50


class AgentState(StrEnum):
    """Real-time state of an agent within a pipeline stage."""

    IDLE = "idle"
    THINKING = "thinking"
    TOOL_USE = "tool_use"
    REVIEWING = "reviewing"
    HANDING_OFF = "handing_off"
    DONE = "done"
    ERROR = "error"


@dataclass(frozen=True)
class AgentPresence:
    """Immutable snapshot of an agent's current presence."""

    agent_id: str
    display_name: str
    stage: str
    state: AgentState = AgentState.IDLE
    activity: str = ""
    model: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    tokens_used: int = 0
    target_agent: str = ""


@dataclass(frozen=True)
class ConversationEntry:
    """A single entry in the agent conversation feed."""

    agent_id: str
    display_name: str
    stage: str
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    target_agent: str = ""


class AgentPresenceTracker:
    """Tracks per-project agent presence and conversation ring buffer.

    Agent presence records are immutable (:class:`AgentPresence`);
    updates rebuild the record via ``dataclasses.replace``.  The
    conversation feed is a bounded ring buffer (default 50 entries).
    """

    def __init__(self, max_conversation_entries: int = DEFAULT_MAX_CONVERSATION) -> None:
        self._max = max_conversation_entries
        self._agents: dict[str, dict[str, AgentPresence]] = {}
        self._conversations: dict[str, tuple[ConversationEntry, ...]] = {}

    # ── Agent state ──────────────────────────────────────────────────

    def update_agent(
        self,
        project_id: str,
        agent_id: str,
        *,
        display_name: str = "",
        stage: str = "",
        state: AgentState = AgentState.IDLE,
        activity: str = "",
        model: str = "",
        tokens_used: int = 0,
        target_agent: str = "",
    ) -> AgentPresence:
        """Create or replace an agent's presence record."""
        presence = AgentPresence(
            agent_id=agent_id,
            display_name=display_name,
            stage=stage,
            state=state,
            activity=activity,
            model=model,
            tokens_used=tokens_used,
            target_agent=target_agent,
        )
        if project_id not in self._agents:
            self._agents[project_id] = {}
        self._agents[project_id][agent_id] = presence
        return presence

    def remove_agent(self, project_id: str, agent_id: str) -> None:
        """Remove an agent from the tracker.  Safe if not present."""
        agents = self._agents.get(project_id)
        if agents is not None:
            agents.pop(agent_id, None)

    def get_agents(self, project_id: str) -> tuple[AgentPresence, ...]:
        """Return all agents for *project_id*, sorted by stage then agent_id."""
        agents = self._agents.get(project_id, {})
        return tuple(sorted(agents.values(), key=lambda a: (a.stage, a.agent_id)))

    # ── Conversation ring buffer ─────────────────────────────────────

    def add_conversation(self, project_id: str, entry: ConversationEntry) -> None:
        """Append an entry, trimming oldest when the buffer is full."""
        existing = self._conversations.get(project_id, ())
        updated = (*existing, entry)
        if len(updated) > self._max:
            updated = updated[len(updated) - self._max :]
        self._conversations[project_id] = updated

    def get_conversation(self, project_id: str) -> tuple[ConversationEntry, ...]:
        """Return the conversation ring buffer for *project_id*."""
        return self._conversations.get(project_id, ())

    # ── Lifecycle ────────────────────────────────────────────────────

    def clear(self, project_id: str) -> None:
        """Remove all state for *project_id*."""
        self._agents.pop(project_id, None)
        self._conversations.pop(project_id, None)

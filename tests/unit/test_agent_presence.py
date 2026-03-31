"""Tests for agent presence tracking (Phase 7)."""

from __future__ import annotations

import dataclasses
from datetime import datetime

import pytest

from colette.orchestrator.agent_presence import (
    AgentPresence,
    AgentPresenceTracker,
    AgentState,
    ConversationEntry,
)

# ── AgentState StrEnum ──────────────────────────────────────────────


class TestAgentState:
    def test_values(self) -> None:
        assert AgentState.IDLE == "idle"
        assert AgentState.THINKING == "thinking"
        assert AgentState.TOOL_USE == "tool_use"
        assert AgentState.REVIEWING == "reviewing"
        assert AgentState.HANDING_OFF == "handing_off"
        assert AgentState.DONE == "done"
        assert AgentState.ERROR == "error"

    def test_string_comparison(self) -> None:
        assert AgentState.THINKING == "thinking"
        assert str(AgentState.TOOL_USE) == "tool_use"


# ── AgentPresence frozen dataclass ──────────────────────────────────


class TestAgentPresence:
    def test_defaults(self) -> None:
        p = AgentPresence(agent_id="a", display_name="Agent A", stage="design")
        assert p.state == AgentState.IDLE
        assert p.activity == ""
        assert p.model == ""
        assert p.tokens_used == 0
        assert p.target_agent == ""

    def test_frozen(self) -> None:
        p = AgentPresence(agent_id="a", display_name="A", stage="design")
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.state = AgentState.THINKING  # type: ignore[misc]

    def test_custom_values(self) -> None:
        p = AgentPresence(
            agent_id="design.architect",
            display_name="System Architect",
            stage="design",
            state=AgentState.THINKING,
            activity="Designing schema",
            model="claude-sonnet",
            tokens_used=500,
            target_agent="api_designer",
        )
        assert p.state == AgentState.THINKING
        assert p.target_agent == "api_designer"


# ── ConversationEntry frozen dataclass ──────────────────────────────


class TestConversationEntry:
    def test_defaults(self) -> None:
        e = ConversationEntry(
            agent_id="a", display_name="Agent A", stage="design", message="hello"
        )
        assert e.target_agent == ""
        assert isinstance(e.timestamp, datetime)

    def test_frozen(self) -> None:
        e = ConversationEntry(
            agent_id="a", display_name="A", stage="design", message="hi"
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            e.message = "changed"  # type: ignore[misc]


# ── AgentPresenceTracker ────────────────────────────────────────────


class TestAgentPresenceTracker:
    def test_update_agent_creates_new(self) -> None:
        tracker = AgentPresenceTracker()
        result = tracker.update_agent(
            "proj-1", "agent.arch",
            display_name="Architect", stage="design", state=AgentState.THINKING,
        )
        assert result.agent_id == "agent.arch"
        assert result.state == AgentState.THINKING
        agents = tracker.get_agents("proj-1")
        assert len(agents) == 1

    def test_update_agent_replaces_existing(self) -> None:
        tracker = AgentPresenceTracker()
        tracker.update_agent(
            "p", "a1", display_name="A1", stage="design", state=AgentState.THINKING,
        )
        tracker.update_agent(
            "p", "a1", display_name="A1", stage="design", state=AgentState.DONE,
        )
        agents = tracker.get_agents("p")
        assert len(agents) == 1
        assert agents[0].state == AgentState.DONE

    def test_remove_agent(self) -> None:
        tracker = AgentPresenceTracker()
        tracker.update_agent("p", "a1", display_name="A1", stage="design")
        tracker.remove_agent("p", "a1")
        assert len(tracker.get_agents("p")) == 0

    def test_remove_nonexistent_agent_no_error(self) -> None:
        tracker = AgentPresenceTracker()
        tracker.remove_agent("p", "does-not-exist")  # should not raise

    def test_get_agents_empty_project(self) -> None:
        tracker = AgentPresenceTracker()
        assert tracker.get_agents("nonexistent") == ()

    def test_get_agents_sorted_by_stage_then_id(self) -> None:
        tracker = AgentPresenceTracker()
        tracker.update_agent("p", "b.agent", display_name="B", stage="implementation")
        tracker.update_agent("p", "a.agent", display_name="A", stage="design")
        tracker.update_agent("p", "c.agent", display_name="C", stage="design")
        agents = tracker.get_agents("p")
        assert [a.agent_id for a in agents] == ["a.agent", "c.agent", "b.agent"]

    def test_ring_buffer_respects_max(self) -> None:
        tracker = AgentPresenceTracker(max_conversation_entries=50)
        for i in range(55):
            tracker.add_conversation(
                "p",
                ConversationEntry(
                    agent_id="a", display_name="A", stage="s", message=f"msg-{i}"
                ),
            )
        convo = tracker.get_conversation("p")
        assert len(convo) == 50
        # Oldest 5 should be trimmed; first remaining is msg-5
        assert convo[0].message == "msg-5"
        assert convo[-1].message == "msg-54"

    def test_ring_buffer_default_max_is_50(self) -> None:
        tracker = AgentPresenceTracker()
        for i in range(60):
            tracker.add_conversation(
                "p",
                ConversationEntry(
                    agent_id="a", display_name="A", stage="s", message=f"m{i}"
                ),
            )
        assert len(tracker.get_conversation("p")) == 50

    def test_ring_buffer_custom_max(self) -> None:
        tracker = AgentPresenceTracker(max_conversation_entries=5)
        for i in range(10):
            tracker.add_conversation(
                "p",
                ConversationEntry(
                    agent_id="a", display_name="A", stage="s", message=f"m{i}"
                ),
            )
        convo = tracker.get_conversation("p")
        assert len(convo) == 5
        assert convo[0].message == "m5"

    def test_get_conversation_empty(self) -> None:
        tracker = AgentPresenceTracker()
        assert tracker.get_conversation("nonexistent") == ()

    def test_clear_removes_all_state(self) -> None:
        tracker = AgentPresenceTracker()
        tracker.update_agent("p", "a1", display_name="A1", stage="design")
        tracker.add_conversation(
            "p",
            ConversationEntry(agent_id="a", display_name="A", stage="s", message="hi"),
        )
        tracker.clear("p")
        assert tracker.get_agents("p") == ()
        assert tracker.get_conversation("p") == ()

    def test_clear_nonexistent_project_no_error(self) -> None:
        tracker = AgentPresenceTracker()
        tracker.clear("nonexistent")  # should not raise

    def test_multiple_projects_isolated(self) -> None:
        tracker = AgentPresenceTracker()
        tracker.update_agent("p1", "a1", display_name="A1", stage="design")
        tracker.update_agent("p2", "a2", display_name="A2", stage="testing")
        tracker.add_conversation(
            "p1",
            ConversationEntry(agent_id="a", display_name="A", stage="s", message="p1"),
        )
        assert len(tracker.get_agents("p1")) == 1
        assert len(tracker.get_agents("p2")) == 1
        assert tracker.get_agents("p1")[0].agent_id == "a1"
        assert tracker.get_agents("p2")[0].agent_id == "a2"
        assert len(tracker.get_conversation("p1")) == 1
        assert len(tracker.get_conversation("p2")) == 0

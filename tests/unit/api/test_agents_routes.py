"""Tests for agent presence and conversation REST endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from colette.api.routes.agents import router
from colette.orchestrator.agent_presence import (
    AgentPresenceTracker,
    AgentState,
    ConversationEntry,
)


@pytest.fixture
def app() -> FastAPI:
    """Minimal FastAPI app with the agents router mounted."""
    app = FastAPI()
    app.include_router(router, prefix="/projects")
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture
def tracker() -> AgentPresenceTracker:
    return AgentPresenceTracker()


@pytest.fixture
def mock_runner() -> MagicMock:
    runner = MagicMock()
    runner.is_active.return_value = True
    runner.get_progress = AsyncMock()
    return runner


class TestGetAgents:
    def test_returns_empty_list_for_active_project(
        self, client: TestClient, tracker: AgentPresenceTracker, mock_runner: MagicMock
    ) -> None:
        with (
            patch("colette.api.routes.agents.get_tracker", return_value=tracker),
            patch("colette.api.routes.agents.get_pipeline_runner", return_value=mock_runner),
            patch("colette.api.routes.agents.get_settings"),
        ):
            resp = client.get("/projects/proj-1/agents")
        assert resp.status_code == 200
        assert resp.json() == {"agents": []}

    def test_returns_agent_list(
        self, client: TestClient, tracker: AgentPresenceTracker, mock_runner: MagicMock
    ) -> None:
        tracker.update_agent(
            "proj-1",
            "agent-a",
            display_name="Analyst",
            stage="requirements",
            state=AgentState.THINKING,
            activity="Analyzing requirements",
            model="claude-sonnet-4-6",
            tokens_used=1500,
        )
        with (
            patch("colette.api.routes.agents.get_tracker", return_value=tracker),
            patch("colette.api.routes.agents.get_pipeline_runner", return_value=mock_runner),
            patch("colette.api.routes.agents.get_settings"),
        ):
            resp = client.get("/projects/proj-1/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["agents"]) == 1
        agent = data["agents"][0]
        assert agent["agent_id"] == "agent-a"
        assert agent["display_name"] == "Analyst"
        assert agent["stage"] == "requirements"
        assert agent["state"] == "thinking"
        assert agent["tokens_used"] == 1500

    def test_404_for_nonexistent_project(
        self, client: TestClient, tracker: AgentPresenceTracker
    ) -> None:
        runner = MagicMock()
        runner.is_active.return_value = False
        runner.get_progress = AsyncMock(side_effect=Exception("not found"))
        with (
            patch("colette.api.routes.agents.get_tracker", return_value=tracker),
            patch("colette.api.routes.agents.get_pipeline_runner", return_value=runner),
            patch("colette.api.routes.agents.get_settings"),
        ):
            resp = client.get("/projects/nonexistent/agents")
        assert resp.status_code == 404


class TestGetConversation:
    def test_returns_empty_entries_for_active_project(
        self, client: TestClient, tracker: AgentPresenceTracker, mock_runner: MagicMock
    ) -> None:
        with (
            patch("colette.api.routes.agents.get_tracker", return_value=tracker),
            patch("colette.api.routes.agents.get_pipeline_runner", return_value=mock_runner),
            patch("colette.api.routes.agents.get_settings"),
        ):
            resp = client.get("/projects/proj-1/conversation")
        assert resp.status_code == 200
        assert resp.json() == {"entries": []}

    def test_returns_conversation_entries(
        self, client: TestClient, tracker: AgentPresenceTracker, mock_runner: MagicMock
    ) -> None:
        ts = datetime(2026, 4, 5, 12, 0, 0, tzinfo=UTC)
        tracker.add_conversation(
            "proj-1",
            ConversationEntry(
                agent_id="agent-a",
                display_name="Analyst",
                stage="requirements",
                message="Starting analysis",
                timestamp=ts,
            ),
        )
        tracker.add_conversation(
            "proj-1",
            ConversationEntry(
                agent_id="agent-b",
                display_name="Reviewer",
                stage="requirements",
                message="Reviewing output",
                timestamp=ts,
            ),
        )
        with (
            patch("colette.api.routes.agents.get_tracker", return_value=tracker),
            patch("colette.api.routes.agents.get_pipeline_runner", return_value=mock_runner),
            patch("colette.api.routes.agents.get_settings"),
        ):
            resp = client.get("/projects/proj-1/conversation")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["entries"]) == 2
        assert data["entries"][0]["agent_id"] == "agent-a"
        assert data["entries"][1]["message"] == "Reviewing output"

    def test_404_for_nonexistent_project(
        self, client: TestClient, tracker: AgentPresenceTracker
    ) -> None:
        runner = MagicMock()
        runner.is_active.return_value = False
        runner.get_progress = AsyncMock(side_effect=Exception("not found"))
        with (
            patch("colette.api.routes.agents.get_tracker", return_value=tracker),
            patch("colette.api.routes.agents.get_pipeline_runner", return_value=runner),
            patch("colette.api.routes.agents.get_settings"),
        ):
            resp = client.get("/projects/nonexistent/conversation")
        assert resp.status_code == 404

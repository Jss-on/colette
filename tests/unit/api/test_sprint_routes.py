"""Tests for sprint lifecycle API routes (Phase 4)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from colette.api.routes.sprints import router
from colette.services.backlog_manager import BacklogManager


@pytest.fixture(autouse=True)
def _fresh_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    fresh = BacklogManager()
    monkeypatch.setattr("colette.api.routes.sprints._manager", fresh)


@pytest.fixture
def client() -> TestClient:
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router, prefix="/projects")
    return TestClient(app)


def _create_sprint(client: TestClient, project_id: str = "proj-1") -> dict:
    """Helper to create a sprint via the backlog manager directly."""
    from colette.api.routes.sprints import get_manager

    mgr = get_manager()
    sprint = mgr.create_sprint(project_id, "MVP", [])
    return sprint.model_dump()


class TestStartSprint:
    def test_starts_sprint(self, client: TestClient) -> None:
        sprint = _create_sprint(client)
        resp = client.post(f"/projects/proj-1/sprints/{sprint['number']}/start")
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    def test_start_nonexistent(self, client: TestClient) -> None:
        resp = client.post("/projects/proj-1/sprints/99/start")
        assert resp.status_code == 404


class TestCompleteSprint:
    def test_completes_sprint(self, client: TestClient) -> None:
        sprint = _create_sprint(client)
        # Start first
        client.post(f"/projects/proj-1/sprints/{sprint['number']}/start")
        resp = client.post(f"/projects/proj-1/sprints/{sprint['number']}/complete")
        assert resp.status_code == 200
        assert resp.json()["status"] == "complete"

    def test_complete_nonexistent(self, client: TestClient) -> None:
        resp = client.post("/projects/proj-1/sprints/99/complete")
        assert resp.status_code == 404


class TestSprintStatus:
    def test_returns_status(self, client: TestClient) -> None:
        sprint = _create_sprint(client)
        resp = client.get(f"/projects/proj-1/sprints/{sprint['number']}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "planning"
        assert data["goal"] == "MVP"

    def test_nonexistent(self, client: TestClient) -> None:
        resp = client.get("/projects/proj-1/sprints/99/status")
        assert resp.status_code == 404

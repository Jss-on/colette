"""Tests for backlog API routes (Phase 3)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from colette.api.routes.backlog import router
from colette.services.backlog_manager import BacklogManager


@pytest.fixture(autouse=True)
def _fresh_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure each test gets a fresh BacklogManager."""
    fresh = BacklogManager()
    monkeypatch.setattr("colette.api.routes.backlog._manager", fresh)


@pytest.fixture
def client() -> TestClient:
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router, prefix="/projects")
    return TestClient(app)


class TestAddWorkItem:
    def test_creates_item(self, client: TestClient) -> None:
        resp = client.post(
            "/projects/proj-1/backlog",
            json={
                "type": "feature",
                "title": "Add login",
                "description": "Login page",
                "priority": "p1_high",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Add login"
        assert data["status"] == "backlog"


class TestGetBacklog:
    def test_empty_backlog(self, client: TestClient) -> None:
        resp = client.get("/projects/proj-1/backlog")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []

    def test_with_items(self, client: TestClient) -> None:
        client.post(
            "/projects/proj-1/backlog",
            json={
                "type": "feature",
                "title": "A",
                "description": "desc",
                "priority": "p2_medium",
            },
        )
        resp = client.get("/projects/proj-1/backlog")
        assert len(resp.json()["items"]) == 1


class TestCreateSprint:
    def test_creates_sprint(self, client: TestClient) -> None:
        # Create an item first
        item_resp = client.post(
            "/projects/proj-1/backlog",
            json={
                "type": "feature",
                "title": "Item",
                "description": "desc",
                "priority": "p1_high",
            },
        )
        item_id = item_resp.json()["id"]

        resp = client.post(
            "/projects/proj-1/sprints",
            json={"goal": "MVP", "work_item_ids": [item_id]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["goal"] == "MVP"
        assert data["number"] == 1


class TestListSprints:
    def test_lists_sprints(self, client: TestClient) -> None:
        client.post(
            "/projects/proj-1/sprints",
            json={"goal": "Sprint 1", "work_item_ids": []},
        )
        resp = client.get("/projects/proj-1/sprints")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestGetSprint:
    def test_existing_sprint(self, client: TestClient) -> None:
        create_resp = client.post(
            "/projects/proj-1/sprints",
            json={"goal": "MVP", "work_item_ids": []},
        )
        sprint_id = create_resp.json()["id"]
        resp = client.get(f"/projects/proj-1/sprints/{sprint_id}")
        assert resp.status_code == 200
        assert resp.json()["goal"] == "MVP"

    def test_nonexistent_sprint(self, client: TestClient) -> None:
        resp = client.get("/projects/proj-1/sprints/FAKE")
        assert resp.status_code == 404

"""Tests for bug report API routes (Phase 5)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from colette.api.routes.bugs import router


@pytest.fixture(autouse=True)
def _fresh_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("colette.api.routes.bugs._bug_store", {})


@pytest.fixture
def client() -> TestClient:
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router, prefix="/projects")
    return TestClient(app)


class TestSubmitBug:
    def test_creates_bug(self, client: TestClient) -> None:
        resp = client.post(
            "/projects/proj-1/bugs",
            json={
                "title": "Crash",
                "description": "App crashes on empty input",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Crash"
        assert data["id"].startswith("BUG-")


class TestListBugs:
    def test_empty(self, client: TestClient) -> None:
        resp = client.get("/projects/proj-1/bugs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_with_bugs(self, client: TestClient) -> None:
        client.post(
            "/projects/proj-1/bugs",
            json={"title": "Bug 1", "description": "d"},
        )
        resp = client.get("/projects/proj-1/bugs")
        assert len(resp.json()) == 1


class TestGetBug:
    def test_existing(self, client: TestClient) -> None:
        create_resp = client.post(
            "/projects/proj-1/bugs",
            json={"title": "Bug", "description": "d"},
        )
        bug_id = create_resp.json()["id"]
        resp = client.get(f"/projects/proj-1/bugs/{bug_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Bug"

    def test_nonexistent(self, client: TestClient) -> None:
        resp = client.get("/projects/proj-1/bugs/FAKE")
        assert resp.status_code == 404

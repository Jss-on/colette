"""Tests for API route assembly."""

from __future__ import annotations

from colette.api.routes import api_router, health_router


class TestRouteAssembly:
    def test_api_router_has_prefix(self) -> None:
        assert api_router.prefix == "/api/v1"

    def test_health_router_exists(self) -> None:
        assert health_router is not None

    def test_api_router_has_project_routes(self) -> None:
        paths = [r.path for r in api_router.routes]
        assert any("/projects" in p for p in paths)

    def test_api_router_has_approval_routes(self) -> None:
        paths = [r.path for r in api_router.routes]
        assert any("/approvals" in p for p in paths)

    def test_api_router_has_artifact_routes(self) -> None:
        paths = [r.path for r in api_router.routes]
        assert any("/artifacts" in p for p in paths)

    def test_api_router_has_pipeline_routes(self) -> None:
        paths = [r.path for r in api_router.routes]
        assert any("/pipeline" in p for p in paths)

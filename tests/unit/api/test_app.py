"""Tests for FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI

from colette.api.app import create_app
from colette.config import Settings


class TestCreateApp:
    def test_returns_fastapi_instance(self) -> None:
        app = create_app(Settings())
        assert isinstance(app, FastAPI)

    def test_app_title(self) -> None:
        app = create_app(Settings())
        assert app.title == "Colette API"

    def test_app_has_routes(self) -> None:
        app = create_app(Settings())
        paths = [r.path for r in app.routes]
        assert "/health" in paths

    def test_app_has_api_prefix(self) -> None:
        app = create_app(Settings())
        paths = [r.path for r in app.routes]
        api_paths = [p for p in paths if p.startswith("/api/v1")]
        assert len(api_paths) > 0

    def test_cors_middleware_added(self) -> None:
        app = create_app(Settings(cors_origins=["http://localhost:3000"]))
        middleware_classes = [m.cls.__name__ for m in app.user_middleware]
        assert "CORSMiddleware" in middleware_classes

    def test_default_settings_used_when_none(self) -> None:
        app = create_app()
        assert isinstance(app, FastAPI)

    def test_openapi_url(self) -> None:
        app = create_app(Settings())
        assert app.openapi_url == "/api/v1/openapi.json"

"""Tests for health check endpoints."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from colette.api.app import create_app
from colette.config import Settings


@pytest.fixture
def app():  # type: ignore[no-untyped-def]
    settings = Settings(rbac_enabled=False, debug=True)
    return create_app(settings)


@pytest.mark.asyncio
async def test_liveness(app) -> None:  # type: ignore[no-untyped-def]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "version" in data


@pytest.mark.asyncio
@pytest.mark.integration
async def test_readiness_requires_db() -> None:
    """Readiness endpoint requires DB — tested in integration tests only."""
    pytest.skip("Readiness check requires a running database.")

"""Shared test fixtures."""

from __future__ import annotations

import pytest

from colette.config import Settings


@pytest.fixture
def settings() -> Settings:
    """Return a Settings instance with test defaults."""
    return Settings(
        database_url="postgresql+asyncpg://test:test@localhost:5432/colette_test",
        redis_url="redis://localhost:6379/1",
        debug=True,
        log_level="DEBUG",
    )

"""Shared test fixtures."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from colette.config import Settings
from colette.memory.config import MemorySettings
from colette.memory.knowledge_graph import NullKnowledgeGraphStore
from colette.memory.project_memory import Mem0ProjectMemoryStore


@pytest.fixture
def settings() -> Settings:
    """Return a Settings instance with test defaults."""
    return Settings(
        database_url="postgresql+asyncpg://test:test@localhost:5432/colette_test",
        redis_url="redis://localhost:6379/1",
        debug=True,
        log_level="DEBUG",
    )


@pytest.fixture
def memory_settings() -> MemorySettings:
    """Return a MemorySettings instance with test defaults."""
    return MemorySettings(
        knowledge_graph_enabled=False,
        cohere_api_key="",
        decay_enabled=False,
    )


@pytest.fixture
def mock_project_memory(memory_settings: MemorySettings) -> Mem0ProjectMemoryStore:
    """Return a Mem0ProjectMemoryStore with a mocked client."""
    store = Mem0ProjectMemoryStore(memory_settings)
    store._client = MagicMock()
    return store


@pytest.fixture
def mock_knowledge_graph() -> NullKnowledgeGraphStore:
    """Return a NullKnowledgeGraphStore for testing without Neo4j."""
    return NullKnowledgeGraphStore()

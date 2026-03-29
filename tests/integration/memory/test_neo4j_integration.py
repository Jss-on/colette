"""Integration tests for Neo4j knowledge graph (requires Neo4j).

Run with: pytest -m integration tests/integration/memory/
Requires: docker-compose up (neo4j)
"""

from __future__ import annotations

import pytest

from colette.memory.config import MemorySettings
from colette.memory.knowledge_graph import (
    GraphitiKnowledgeGraphStore,
    NullKnowledgeGraphStore,
)
from colette.memory.models import KGEntity

pytestmark = [pytest.mark.integration, pytest.mark.slow]


class TestNeo4jIntegration:
    async def test_add_and_get_entity(self) -> None:
        settings = MemorySettings(knowledge_graph_enabled=True)
        store = GraphitiKnowledgeGraphStore(settings)

        entity = KGEntity(
            id="int-e1",
            project_id="integration-test",
            entity_type="module",
            name="colette.memory",
        )
        result = await store.add_entity(entity)
        assert result == "int-e1"

        fetched = await store.get_entity("int-e1")
        assert fetched is not None
        assert fetched.name == "colette.memory"

    async def test_soft_delete(self) -> None:
        settings = MemorySettings(knowledge_graph_enabled=True)
        store = GraphitiKnowledgeGraphStore(settings)

        entity = KGEntity(
            id="int-e2",
            project_id="integration-test",
            entity_type="function",
            name="to_delete",
        )
        await store.add_entity(entity)
        await store.delete_entity("int-e2")

        fetched = await store.get_entity("int-e2")
        assert fetched is None  # soft-deleted, so not returned


class TestNullFallback:
    async def test_null_store_returns_empty(self) -> None:
        store = NullKnowledgeGraphStore()
        assert await store.get_entity("anything") is None
        assert await store.get_neighbors("anything") == []

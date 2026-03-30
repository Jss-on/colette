"""Tests for knowledge graph stores (FR-MEM-002/008)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from colette.memory.config import MemorySettings
from colette.memory.exceptions import (
    KnowledgeGraphUnavailableError,
    MemoryBackendError,
)
from colette.memory.knowledge_graph import (
    GraphitiKnowledgeGraphStore,
    NullKnowledgeGraphStore,
)
from colette.memory.models import KGEntity, KGRelationship


class TestNullKnowledgeGraphStore:
    @pytest.fixture
    def null_store(self) -> NullKnowledgeGraphStore:
        return NullKnowledgeGraphStore()

    async def test_add_entity_returns_id(self, null_store: NullKnowledgeGraphStore) -> None:
        entity = KGEntity(id="e1", project_id="p1", entity_type="func", name="foo")
        result = await null_store.add_entity(entity)
        assert result == "e1"

    async def test_add_relationship_returns_id(self, null_store: NullKnowledgeGraphStore) -> None:
        rel = KGRelationship(
            id="r1",
            project_id="p1",
            source_id="e1",
            target_id="e2",
            relationship_type="imports",
        )
        result = await null_store.add_relationship(rel)
        assert result == "r1"

    async def test_get_entity_returns_none(self, null_store: NullKnowledgeGraphStore) -> None:
        assert await null_store.get_entity("e1") is None

    async def test_get_neighbors_returns_empty(self, null_store: NullKnowledgeGraphStore) -> None:
        assert await null_store.get_neighbors("e1") == []

    async def test_query_temporal_returns_empty(self, null_store: NullKnowledgeGraphStore) -> None:
        result = await null_store.query_temporal("p1", since=datetime.now(UTC))
        assert result == []

    async def test_delete_entity_noop(self, null_store: NullKnowledgeGraphStore) -> None:
        await null_store.delete_entity("e1")


class TestGraphitiKnowledgeGraphStore:
    def test_disabled_raises(self) -> None:
        settings = MemorySettings(knowledge_graph_enabled=False)
        with pytest.raises(KnowledgeGraphUnavailableError):
            GraphitiKnowledgeGraphStore(settings)

    def test_enabled_creates_instance(self) -> None:
        settings = MemorySettings(knowledge_graph_enabled=True)
        store = GraphitiKnowledgeGraphStore(settings)
        assert store._driver is None  # lazy init

    async def test_add_entity_calls_neo4j(self) -> None:
        settings = MemorySettings(knowledge_graph_enabled=True)
        store = GraphitiKnowledgeGraphStore(settings)

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session
        store._driver = mock_driver

        entity = KGEntity(id="e1", project_id="p1", entity_type="class", name="MyClass")
        result = await store.add_entity(entity)
        assert result == "e1"
        mock_session.run.assert_called_once()

    async def test_add_entity_wraps_exception(self) -> None:
        settings = MemorySettings(knowledge_graph_enabled=True)
        store = GraphitiKnowledgeGraphStore(settings)

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.run.side_effect = RuntimeError("neo4j down")

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session
        store._driver = mock_driver

        entity = KGEntity(id="e1", project_id="p1", entity_type="func", name="foo")
        with pytest.raises(MemoryBackendError, match="neo4j"):
            await store.add_entity(entity)

    async def test_get_entity_returns_none_when_not_found(self) -> None:
        settings = MemorySettings(knowledge_graph_enabled=True)
        store = GraphitiKnowledgeGraphStore(settings)

        mock_result = MagicMock()
        mock_result.single.return_value = None

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.run.return_value = mock_result

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session
        store._driver = mock_driver

        result = await store.get_entity("nonexistent")
        assert result is None

    async def test_delete_entity_sets_expired_at(self) -> None:
        settings = MemorySettings(knowledge_graph_enabled=True)
        store = GraphitiKnowledgeGraphStore(settings)

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session
        store._driver = mock_driver

        await store.delete_entity("e1")
        mock_session.run.assert_called_once()
        call_args = mock_session.run.call_args
        assert "expired_at" in call_args[0][0]

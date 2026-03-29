"""Tests for MemoryManager facade."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from colette.memory.config import MemorySettings
from colette.memory.context.budget_tracker import ContextBudgetTracker
from colette.memory.context.compactor import VerbatimCompactor
from colette.memory.context.history_manager import HistoryManager
from colette.memory.knowledge_graph import NullKnowledgeGraphStore
from colette.memory.manager import MemoryManager
from colette.memory.models import (
    ChunkRecord,
    KGEntity,
    MemoryWriteResult,
    RetrievalResult,
)
from colette.memory.project_memory import Mem0ProjectMemoryStore
from colette.memory.rag.evaluator import RAGTriadEvaluator
from colette.memory.rag.reranker import NoOpReranker
from colette.memory.write_pipeline import MemoryWritePipeline, WriteDecision


@pytest.fixture
def settings() -> MemorySettings:
    return MemorySettings(
        knowledge_graph_enabled=False,
        cohere_api_key="",
    )


@pytest.fixture
def mock_write_pipeline() -> AsyncMock:
    pipeline = AsyncMock(spec=MemoryWritePipeline)
    pipeline.process_write = AsyncMock(return_value=[
        WriteDecision(fact="test", result=MemoryWriteResult.ADDED, new_id="new-1")
    ])
    return pipeline


@pytest.fixture
def mock_retriever() -> AsyncMock:
    retriever = AsyncMock()
    chunk = ChunkRecord(
        id="c1", project_id="p1", source_path="a.py",
        content="test content", token_count=5,
        chunk_index=0, total_chunks=1,
    )
    retriever.retrieve = AsyncMock(return_value=[
        RetrievalResult(chunk=chunk, score=0.9, source="rrf")
    ])
    return retriever


@pytest.fixture
def manager(
    settings: MemorySettings,
    mock_write_pipeline: AsyncMock,
    mock_retriever: AsyncMock,
) -> MemoryManager:
    return MemoryManager(
        settings=settings,
        project_memory=MagicMock(spec=Mem0ProjectMemoryStore),
        knowledge_graph=NullKnowledgeGraphStore(),
        write_pipeline=mock_write_pipeline,
        retriever=mock_retriever,
        reranker=NoOpReranker(),
        evaluator=RAGTriadEvaluator(settings),
        compactor=VerbatimCompactor(),
    )


class TestStoreMemory:
    async def test_delegates_to_write_pipeline(
        self,
        manager: MemoryManager,
        mock_write_pipeline: AsyncMock,
    ) -> None:
        decisions = await manager.store_memory("proj-1", "new fact")
        mock_write_pipeline.process_write.assert_called_once()
        assert len(decisions) == 1
        assert decisions[0].result == MemoryWriteResult.ADDED


class TestRetrieveContext:
    async def test_returns_reranked_results(
        self,
        manager: MemoryManager,
        mock_retriever: AsyncMock,
    ) -> None:
        results = await manager.retrieve_context("proj-1", "test query")
        mock_retriever.retrieve.assert_called_once()
        assert len(results) >= 1


class TestBudgetTracker:
    def test_create_budget_tracker(self, manager: MemoryManager) -> None:
        tracker = manager.create_budget_tracker("test_agent", 100_000)
        assert isinstance(tracker, ContextBudgetTracker)
        assert tracker.agent_role == "test_agent"
        assert tracker.total_budget == 100_000

    def test_compact_if_needed_no_compaction(self, manager: MemoryManager) -> None:
        tracker = manager.create_budget_tracker("test", 100_000)
        content, result = manager.compact_if_needed("short text", tracker)
        assert content == "short text"
        assert result is None

    def test_compact_if_needed_triggers(self, manager: MemoryManager) -> None:
        tracker = manager.create_budget_tracker("test", 100_000)
        # Force high utilization (>70%)
        tracker = tracker.record_usage("history", 15_000)
        tracker = tracker.record_usage("retrieved_context", 35_000)
        tracker = tracker.record_usage("output", 21_000)
        # Build content larger than 50% of budget (50K tokens = ~200K chars)
        # The compactor target is 50% of total_budget = 50K tokens
        paragraphs = [f"Paragraph {i}: " + "word " * 200 for i in range(100)]
        content = "\n\n".join(paragraphs)
        _compacted, result = manager.compact_if_needed(content, tracker)
        assert result is not None
        assert result.compacted_tokens <= 50_000


class TestHistoryManager:
    def test_create_history_manager(self, manager: MemoryManager) -> None:
        hm = manager.create_history_manager()
        assert isinstance(hm, HistoryManager)
        assert hm.recent_count == 10

    def test_custom_recent_count(self, manager: MemoryManager) -> None:
        hm = manager.create_history_manager(recent_count=5)
        assert hm.recent_count == 5


class TestKnowledgeGraph:
    async def test_add_entity(self, manager: MemoryManager) -> None:
        entity = KGEntity(
            id="e1", project_id="p1", entity_type="func", name="foo"
        )
        result = await manager.add_to_knowledge_graph(entity)
        assert result == "e1"

    async def test_query_returns_empty_for_null(
        self, manager: MemoryManager
    ) -> None:
        results = await manager.query_knowledge_graph("e1")
        assert results == []

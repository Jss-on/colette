"""Tests for reranker (FR-MEM-007)."""

from __future__ import annotations

from unittest.mock import MagicMock

from colette.memory.config import MemorySettings
from colette.memory.models import ChunkRecord, RetrievalResult
from colette.memory.rag.reranker import CohereReranker, NoOpReranker, create_reranker


def _make_result(chunk_id: str, score: float) -> RetrievalResult:
    chunk = ChunkRecord(
        id=chunk_id,
        project_id="p1",
        source_path="a.py",
        content=f"content {chunk_id}",
        token_count=10,
        chunk_index=0,
        total_chunks=1,
    )
    return RetrievalResult(chunk=chunk, score=score, source="rrf")


class TestNoOpReranker:
    async def test_truncates_to_top_n(self) -> None:
        reranker = NoOpReranker()
        results = [_make_result(str(i), float(i)) for i in range(10)]
        reranked = await reranker.rerank("query", results, top_n=3)
        assert len(reranked) == 3

    async def test_empty_results(self) -> None:
        reranker = NoOpReranker()
        reranked = await reranker.rerank("query", [], top_n=5)
        assert reranked == []


class TestCohereReranker:
    async def test_falls_back_to_noop_when_no_key(self) -> None:
        settings = MemorySettings(cohere_api_key="")
        reranker = CohereReranker(settings)
        results = [_make_result(str(i), float(i)) for i in range(10)]
        reranked = await reranker.rerank("query", results, top_n=3)
        assert len(reranked) == 3

    async def test_empty_candidates(self) -> None:
        settings = MemorySettings(cohere_api_key="test-key")
        reranker = CohereReranker(settings)
        reranked = await reranker.rerank("query", [], top_n=5)
        assert reranked == []

    async def test_rerank_with_mock_client(self) -> None:
        settings = MemorySettings(cohere_api_key="test-key")
        reranker = CohereReranker(settings)

        mock_item_0 = MagicMock()
        mock_item_0.index = 1
        mock_item_0.relevance_score = 0.95
        mock_item_1 = MagicMock()
        mock_item_1.index = 0
        mock_item_1.relevance_score = 0.80

        mock_response = MagicMock()
        mock_response.results = [mock_item_0, mock_item_1]

        mock_client = MagicMock()
        mock_client.rerank.return_value = mock_response
        reranker._client = mock_client

        results = [_make_result("a", 0.5), _make_result("b", 0.6)]
        reranked = await reranker.rerank("test query", results, top_n=2)
        assert len(reranked) == 2
        assert reranked[0].score == 0.95
        assert reranked[0].chunk.id == "b"

    async def test_falls_back_on_api_error(self) -> None:
        settings = MemorySettings(cohere_api_key="test-key")
        reranker = CohereReranker(settings)

        mock_client = MagicMock()
        mock_client.rerank.side_effect = RuntimeError("API error")
        reranker._client = mock_client

        results = [_make_result(str(i), float(i)) for i in range(5)]
        reranked = await reranker.rerank("query", results, top_n=3)
        # Should fall back to NoOp
        assert len(reranked) == 3


class TestCreateReranker:
    def test_no_key_returns_noop(self) -> None:
        reranker = create_reranker(MemorySettings(cohere_api_key=""))
        assert isinstance(reranker, NoOpReranker)

    def test_with_key_returns_cohere(self) -> None:
        reranker = create_reranker(MemorySettings(cohere_api_key="sk-test"))
        assert isinstance(reranker, CohereReranker)

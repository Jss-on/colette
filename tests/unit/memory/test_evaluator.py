"""Tests for RAG Triad evaluator (FR-MEM-013)."""

from __future__ import annotations

import pytest

from colette.memory.config import MemorySettings
from colette.memory.rag.evaluator import RAGTriadEvaluator, _cosine_similarity


class TestCosineSimilarity:
    def test_identical_vectors(self) -> None:
        assert _cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self) -> None:
        assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_empty_vectors(self) -> None:
        assert _cosine_similarity([], []) == 0.0

    def test_different_lengths(self) -> None:
        assert _cosine_similarity([1.0], [1.0, 2.0]) == 0.0

    def test_zero_vectors(self) -> None:
        assert _cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0


class TestRAGTriadEvaluator:
    def _make(self, threshold: float = 0.85) -> RAGTriadEvaluator:
        return RAGTriadEvaluator(MemorySettings(rag_faithfulness_threshold=threshold))

    async def test_basic_evaluation(self) -> None:
        evaluator = self._make()
        result = await evaluator.evaluate(
            query="What is Python?",
            context=["Python is a programming language used for web development."],
            response="Python is a programming language.",
        )
        assert 0.0 <= result.faithfulness <= 1.0
        assert 0.0 <= result.context_relevance <= 1.0
        assert 0.0 <= result.answer_relevance <= 1.0

    async def test_alert_triggered_below_threshold(self) -> None:
        evaluator = self._make(threshold=0.99)
        result = await evaluator.evaluate(
            query="What is quantum computing?",
            context=["Apples are fruit."],
            response="Quantum computing uses qubits for parallel processing.",
        )
        # Response has almost no overlap with context -> low faithfulness
        assert result.alert_triggered is True

    async def test_no_alert_when_faithful(self) -> None:
        evaluator = self._make(threshold=0.3)
        result = await evaluator.evaluate(
            query="What color is the sky?",
            context=["The sky is blue during clear weather."],
            response="The sky is blue.",
        )
        assert result.alert_triggered is False

    async def test_with_embeddings(self) -> None:
        evaluator = self._make()
        result = await evaluator.evaluate(
            query="test",
            context=["context"],
            response="response",
            query_embedding=[1.0, 0.0, 0.0],
            context_embeddings=[[0.9, 0.1, 0.0]],
            response_embedding=[0.8, 0.2, 0.0],
        )
        assert result.context_relevance > 0.0
        assert result.answer_relevance > 0.0

    async def test_empty_context(self) -> None:
        evaluator = self._make()
        result = await evaluator.evaluate(query="test", context=[], response="answer")
        assert result.faithfulness == 0.0

    async def test_empty_response(self) -> None:
        evaluator = self._make()
        result = await evaluator.evaluate(query="test", context=["some context"], response="")
        assert result.faithfulness == 0.0

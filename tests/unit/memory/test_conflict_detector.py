"""Tests for hybrid conflict detector (FR-MEM-009)."""

from __future__ import annotations

import pytest

from colette.memory.conflict_detector import (
    HybridConflictDetector,
    _token_overlap_similarity,
)
from colette.memory.models import ConflictType, MemoryEntry


class TestTokenOverlapSimilarity:
    def test_identical(self) -> None:
        score = _token_overlap_similarity("hello world", "hello world")
        assert score == pytest.approx(1.0)

    def test_no_overlap(self) -> None:
        score = _token_overlap_similarity("hello world", "foo bar")
        assert score == pytest.approx(0.0)

    def test_partial_overlap(self) -> None:
        score = _token_overlap_similarity("hello world test", "hello world foo")
        assert 0.0 < score < 1.0

    def test_empty_strings(self) -> None:
        assert _token_overlap_similarity("", "") == 0.0
        assert _token_overlap_similarity("hello", "") == 0.0


class TestHybridConflictDetector:
    def _make_entry(self, content: str, entry_id: str = "e1") -> MemoryEntry:
        return MemoryEntry(id=entry_id, project_id="p1", content=content)

    async def test_unrelated_content_returns_none(self) -> None:
        detector = HybridConflictDetector()
        existing = self._make_entry("Python uses indentation for blocks")
        result = await detector.detect(existing, "The weather is sunny today")
        assert result is None

    async def test_duplicate_detected_as_same(self) -> None:
        detector = HybridConflictDetector()
        existing = self._make_entry("The API uses REST architecture")
        result = await detector.detect(existing, "The API uses REST architecture")
        assert result is not None
        assert result.conflict_type == ConflictType.SAME

    async def test_similar_content_detected_as_update(self) -> None:
        detector = HybridConflictDetector()
        existing = self._make_entry("The database schema uses PostgreSQL with three main tables")
        result = await detector.detect(
            existing, "The database schema uses PostgreSQL with four main tables and indexes"
        )
        assert result is not None
        assert result.conflict_type in (ConflictType.UPDATE, ConflictType.CONTRADICTION)

    async def test_contradiction_with_negation(self) -> None:
        detector = HybridConflictDetector()
        existing = self._make_entry("The system does use caching for all API responses")
        result = await detector.detect(
            existing, "The system does not use caching for all API responses"
        )
        assert result is not None
        assert result.conflict_type == ConflictType.CONTRADICTION

    async def test_report_has_correct_fields(self) -> None:
        detector = HybridConflictDetector()
        existing = self._make_entry("same content here", entry_id="mem-99")
        result = await detector.detect(existing, "same content here")
        assert result is not None
        assert result.existing_entry.id == "mem-99"
        assert result.incoming_content == "same content here"
        assert result.similarity_score > 0
        assert result.detected_at is not None

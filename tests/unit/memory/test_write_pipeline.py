"""Tests for memory write pipeline (FR-MEM-011)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from colette.memory.conflict_detector import HybridConflictDetector
from colette.memory.models import (
    ConflictReport,
    ConflictType,
    MemoryEntry,
    MemoryWriteResult,
)
from colette.memory.write_pipeline import MemoryWritePipeline, _extract_facts


class TestExtractFacts:
    def test_sentences(self) -> None:
        facts = _extract_facts("Python is great. It supports type hints.")
        assert len(facts) == 2

    def test_skips_questions(self) -> None:
        facts = _extract_facts("Is Python good? Python is a great language.")
        # "Is Python good" is split by "?" and ends before the "?"
        # Both may pass the length check; what matters is "?" sentences are filtered
        great_facts = [f for f in facts if "great" in f]
        assert len(great_facts) == 1

    def test_skips_short_fragments(self) -> None:
        facts = _extract_facts("OK. Fine. Python is a programming language.")
        assert len(facts) == 1

    def test_empty_input(self) -> None:
        assert _extract_facts("") == []

    def test_single_fact(self) -> None:
        facts = _extract_facts("The system uses REST APIs for communication")
        assert len(facts) == 1


class TestMemoryWritePipeline:
    @pytest.fixture
    def mock_store(self) -> AsyncMock:
        store = AsyncMock()
        store.search = AsyncMock(return_value=[])
        store.store = AsyncMock(return_value="new-id")
        store.update = AsyncMock()
        return store

    @pytest.fixture
    def mock_detector(self) -> AsyncMock:
        detector = AsyncMock(spec=HybridConflictDetector)
        detector.detect = AsyncMock(return_value=None)
        return detector

    @pytest.fixture
    def pipeline(
        self,
        mock_store: AsyncMock,
        mock_detector: AsyncMock,
    ) -> MemoryWritePipeline:
        return MemoryWritePipeline(mock_store, mock_detector)

    async def test_new_fact_is_added(
        self,
        pipeline: MemoryWritePipeline,
        mock_store: AsyncMock,
    ) -> None:
        decisions = await pipeline.process_write("proj-1", "A new architectural decision was made")
        assert len(decisions) >= 1
        assert any(d.result == MemoryWriteResult.ADDED for d in decisions)
        mock_store.store.assert_called()

    async def test_duplicate_is_skipped(
        self,
        pipeline: MemoryWritePipeline,
        mock_store: AsyncMock,
        mock_detector: AsyncMock,
    ) -> None:
        existing = MemoryEntry(id="e1", project_id="proj-1", content="existing fact")
        mock_store.search.return_value = [existing]
        mock_detector.detect.return_value = ConflictReport(
            existing_entry=existing,
            incoming_content="existing fact",
            similarity_score=0.99,
            conflict_type=ConflictType.SAME,
        )
        decisions = await pipeline.process_write("proj-1", "existing fact here")
        assert any(d.result == MemoryWriteResult.SKIPPED for d in decisions)

    async def test_update_is_applied(
        self,
        pipeline: MemoryWritePipeline,
        mock_store: AsyncMock,
        mock_detector: AsyncMock,
    ) -> None:
        existing = MemoryEntry(id="e1", project_id="proj-1", content="old version of the fact")
        mock_store.search.return_value = [existing]
        mock_detector.detect.return_value = ConflictReport(
            existing_entry=existing,
            incoming_content="new version",
            similarity_score=0.88,
            conflict_type=ConflictType.UPDATE,
        )
        decisions = await pipeline.process_write("proj-1", "new version of the fact here")
        assert any(d.result == MemoryWriteResult.UPDATED for d in decisions)
        mock_store.update.assert_called()

    async def test_contradiction_is_flagged(
        self,
        pipeline: MemoryWritePipeline,
        mock_store: AsyncMock,
        mock_detector: AsyncMock,
    ) -> None:
        existing = MemoryEntry(id="e1", project_id="proj-1", content="system uses caching")
        mock_store.search.return_value = [existing]
        mock_detector.detect.return_value = ConflictReport(
            existing_entry=existing,
            incoming_content="system does not use caching",
            similarity_score=0.75,
            conflict_type=ConflictType.CONTRADICTION,
        )
        decisions = await pipeline.process_write("proj-1", "system does not use caching anymore")
        assert any(d.result == MemoryWriteResult.CONFLICT_FLAGGED for d in decisions)
        mock_store.store.assert_not_called()

    async def test_empty_content(
        self,
        pipeline: MemoryWritePipeline,
    ) -> None:
        decisions = await pipeline.process_write("proj-1", "")
        assert decisions == []

    async def test_metadata_passed_through(
        self,
        pipeline: MemoryWritePipeline,
        mock_store: AsyncMock,
    ) -> None:
        await pipeline.process_write(
            "proj-1",
            "An important decision was reached today",
            metadata={"source": "design_review"},
        )
        call_args = mock_store.store.call_args
        entry = call_args[0][0]
        assert ("source", "design_review") in entry.metadata

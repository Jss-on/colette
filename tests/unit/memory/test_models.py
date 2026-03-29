"""Tests for memory domain models (FR-MEM-001/002/007)."""

from __future__ import annotations

import pytest

from colette.memory.models import (
    ChunkRecord,
    CompactionResult,
    ConflictReport,
    ConflictType,
    KGEntity,
    KGRelationship,
    MemoryEntry,
    MemoryScope,
    MemoryWriteResult,
    RAGTriadResult,
    RetrievalResult,
)


class TestMemoryScope:
    def test_values(self) -> None:
        assert MemoryScope.PRIVATE == "private"
        assert MemoryScope.SHARED == "shared"
        assert MemoryScope.GLOBAL == "global"


class TestMemoryWriteResult:
    def test_values(self) -> None:
        assert MemoryWriteResult.ADDED == "added"
        assert MemoryWriteResult.CONFLICT_FLAGGED == "conflict_flagged"


class TestConflictType:
    def test_values(self) -> None:
        assert ConflictType.SAME == "same"
        assert ConflictType.UPDATE == "update"
        assert ConflictType.CONTRADICTION == "contradiction"


class TestMemoryEntry:
    def _make(self, **overrides: object) -> MemoryEntry:
        defaults: dict[str, object] = {
            "id": "mem-1",
            "project_id": "proj-1",
            "content": "test content",
        }
        defaults.update(overrides)
        return MemoryEntry(**defaults)  # type: ignore[arg-type]

    def test_frozen(self) -> None:
        entry = self._make()
        with pytest.raises(AttributeError):
            entry.content = "mutated"  # type: ignore[misc]

    def test_defaults(self) -> None:
        entry = self._make()
        assert entry.scope == MemoryScope.SHARED
        assert entry.confidence == 1.0
        assert entry.is_permanent is False
        assert entry.expires_at is None
        assert entry.metadata == ()

    def test_metadata_dict(self) -> None:
        entry = self._make(metadata=(("key", "val"),))
        assert entry.metadata_dict == {"key": "val"}


class TestKGEntity:
    def _make(self, **overrides: object) -> KGEntity:
        defaults: dict[str, object] = {
            "id": "ent-1",
            "project_id": "proj-1",
            "entity_type": "function",
            "name": "my_func",
        }
        defaults.update(overrides)
        return KGEntity(**defaults)  # type: ignore[arg-type]

    def test_frozen(self) -> None:
        entity = self._make()
        with pytest.raises(AttributeError):
            entity.name = "mutated"  # type: ignore[misc]

    def test_bi_temporal_defaults(self) -> None:
        entity = self._make()
        assert entity.created_at is not None
        assert entity.valid_at is not None
        assert entity.expired_at is None
        assert entity.invalid_at is None

    def test_properties_dict(self) -> None:
        entity = self._make(properties=(("lang", "python"),))
        assert entity.properties_dict == {"lang": "python"}


class TestKGRelationship:
    def test_frozen(self) -> None:
        rel = KGRelationship(
            id="rel-1",
            project_id="proj-1",
            source_id="ent-1",
            target_id="ent-2",
            relationship_type="imports",
        )
        with pytest.raises(AttributeError):
            rel.relationship_type = "mutated"  # type: ignore[misc]

    def test_properties_dict(self) -> None:
        rel = KGRelationship(
            id="rel-1",
            project_id="proj-1",
            source_id="ent-1",
            target_id="ent-2",
            relationship_type="imports",
            properties=(("weight", "0.9"),),
        )
        assert rel.properties_dict == {"weight": "0.9"}


class TestChunkRecord:
    def test_frozen(self) -> None:
        chunk = ChunkRecord(
            id="c-1",
            project_id="proj-1",
            source_path="src/main.py",
            content="def foo(): ...",
            token_count=5,
            chunk_index=0,
            total_chunks=1,
        )
        with pytest.raises(AttributeError):
            chunk.content = "mutated"  # type: ignore[misc]


class TestRetrievalResult:
    def test_fields(self) -> None:
        chunk = ChunkRecord(
            id="c-1",
            project_id="proj-1",
            source_path="a.py",
            content="x",
            token_count=1,
            chunk_index=0,
            total_chunks=1,
        )
        result = RetrievalResult(chunk=chunk, score=0.95, source="dense")
        assert result.score == 0.95
        assert result.source == "dense"


class TestConflictReport:
    def test_frozen(self) -> None:
        entry = MemoryEntry(id="m1", project_id="p1", content="old")
        report = ConflictReport(
            existing_entry=entry,
            incoming_content="new contradicts old",
            similarity_score=0.92,
            conflict_type=ConflictType.CONTRADICTION,
        )
        assert report.conflict_type == ConflictType.CONTRADICTION
        with pytest.raises(AttributeError):
            report.similarity_score = 0.5  # type: ignore[misc]


class TestCompactionResult:
    def test_frozen(self) -> None:
        result = CompactionResult(
            original_tokens=1000,
            compacted_tokens=400,
            reduction_ratio=0.6,
            compacted_content="compacted",
        )
        assert result.reduction_ratio == 0.6


class TestRAGTriadResult:
    def test_defaults(self) -> None:
        result = RAGTriadResult(
            faithfulness=0.9,
            context_relevance=0.85,
            answer_relevance=0.88,
        )
        assert result.alert_triggered is False

    def test_alert_triggered(self) -> None:
        result = RAGTriadResult(
            faithfulness=0.7,
            context_relevance=0.85,
            answer_relevance=0.88,
            alert_triggered=True,
        )
        assert result.alert_triggered is True

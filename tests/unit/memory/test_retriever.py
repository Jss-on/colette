"""Tests for hybrid retriever and RRF fusion (FR-MEM-007)."""

from __future__ import annotations

from colette.memory.models import ChunkRecord, RetrievalResult
from colette.memory.rag.retriever import (
    _position_aware_reorder,
    _reciprocal_rank_fusion,
)


def _make_result(chunk_id: str, score: float, source: str = "test") -> RetrievalResult:
    chunk = ChunkRecord(
        id=chunk_id,
        project_id="p1",
        source_path="a.py",
        content=f"content {chunk_id}",
        token_count=10,
        chunk_index=0,
        total_chunks=1,
    )
    return RetrievalResult(chunk=chunk, score=score, source=source)


class TestReciprocalRankFusion:
    def test_merges_two_lists(self) -> None:
        list1 = [_make_result("a", 0.9), _make_result("b", 0.8)]
        list2 = [_make_result("b", 0.95), _make_result("c", 0.7)]
        fused = _reciprocal_rank_fusion([list1, list2])
        ids = [r.chunk.id for r in fused]
        # "b" appears in both lists so should have highest RRF score
        assert ids[0] == "b"
        assert len(fused) == 3

    def test_empty_lists(self) -> None:
        assert _reciprocal_rank_fusion([[], []]) == []

    def test_single_list(self) -> None:
        results = [_make_result("a", 0.9), _make_result("b", 0.8)]
        fused = _reciprocal_rank_fusion([results])
        assert len(fused) == 2
        assert fused[0].chunk.id == "a"

    def test_rrf_scores_are_positive(self) -> None:
        list1 = [_make_result("a", 0.9)]
        list2 = [_make_result("a", 0.8)]
        fused = _reciprocal_rank_fusion([list1, list2])
        assert all(r.score > 0 for r in fused)

    def test_source_is_rrf(self) -> None:
        fused = _reciprocal_rank_fusion([[_make_result("a", 1.0)]])
        assert fused[0].source == "rrf"


class TestPositionAwareReorder:
    def test_small_list_unchanged(self) -> None:
        results = [_make_result("a", 0.9)]
        reordered = _position_aware_reorder(results)
        assert len(reordered) == 1

    def test_two_items_unchanged(self) -> None:
        results = [_make_result("a", 0.9), _make_result("b", 0.8)]
        reordered = _position_aware_reorder(results)
        assert len(reordered) == 2

    def test_highest_scores_at_edges(self) -> None:
        results = [
            _make_result("a", 0.5),
            _make_result("b", 0.9),
            _make_result("c", 0.3),
            _make_result("d", 0.8),
            _make_result("e", 0.1),
        ]
        reordered = _position_aware_reorder(results)
        scores = [r.score for r in reordered]
        # Highest scores should be at start and end
        edge_scores = [scores[0], scores[-1]]
        middle_scores = scores[1:-1]
        assert max(edge_scores) >= max(middle_scores)

    def test_preserves_all_items(self) -> None:
        results = [_make_result(str(i), float(i) / 10) for i in range(10)]
        reordered = _position_aware_reorder(results)
        assert len(reordered) == 10
        original_ids = {r.chunk.id for r in results}
        reordered_ids = {r.chunk.id for r in reordered}
        assert original_ids == reordered_ids

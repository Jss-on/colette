"""Hybrid conflict detection for memory writes (FR-MEM-009).

Uses vector similarity as a pre-filter, then LLM classification
for high-similarity pairs.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog

from colette.memory.models import ConflictReport, ConflictType, MemoryEntry

logger = structlog.get_logger(__name__)

# Similarity threshold to trigger LLM check
_SIMILARITY_THRESHOLD = 0.85


def _token_overlap_similarity(text_a: str, text_b: str) -> float:
    """Simple token overlap as similarity proxy."""
    tokens_a = set(text_a.lower().split())
    tokens_b = set(text_b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union) if union else 0.0


def _classify_conflict(
    existing_content: str,
    incoming_content: str,
    similarity: float,
) -> ConflictType:
    """Classify the relationship between existing and incoming content.

    Uses heuristic analysis.  In production, this should be augmented
    with LLM-based classification using the validation tier model.
    """
    if similarity > 0.95:
        return ConflictType.SAME

    # Check for negation patterns that indicate contradiction
    existing_lower = existing_content.lower()
    incoming_lower = incoming_content.lower()
    negation_markers = ("not ", "no ", "never ", "don't ", "doesn't ", "isn't ", "aren't ")

    existing_has_neg = any(m in existing_lower for m in negation_markers)
    incoming_has_neg = any(m in incoming_lower for m in negation_markers)

    if existing_has_neg != incoming_has_neg and similarity > 0.5:
        return ConflictType.CONTRADICTION

    # High similarity without contradiction suggests an update
    if similarity > _SIMILARITY_THRESHOLD:
        return ConflictType.UPDATE

    return ConflictType.UPDATE


class HybridConflictDetector:
    """Detects conflicts between existing and incoming memory content.

    Step 1: Token overlap similarity as a fast pre-filter.
    Step 2: If similarity is high, classify as SAME/UPDATE/CONTRADICTION.

    Implements the ConflictDetector protocol.
    """

    def __init__(self, similarity_threshold: float = _SIMILARITY_THRESHOLD) -> None:
        self._threshold = similarity_threshold

    async def detect(
        self,
        existing: MemoryEntry,
        incoming_content: str,
    ) -> ConflictReport | None:
        """Check for conflict between existing entry and incoming content.

        Returns ConflictReport if related content is detected, None if
        the content is unrelated.
        """
        similarity = _token_overlap_similarity(existing.content, incoming_content)

        if similarity < 0.3:
            # Content is unrelated — no conflict
            return None

        conflict_type = _classify_conflict(existing.content, incoming_content, similarity)

        logger.info(
            "conflict_detected",
            existing_id=existing.id,
            similarity=round(similarity, 3),
            conflict_type=conflict_type.value,
        )

        return ConflictReport(
            existing_entry=existing,
            incoming_content=incoming_content,
            similarity_score=round(similarity, 3),
            conflict_type=conflict_type,
            detected_at=datetime.now(UTC),
        )

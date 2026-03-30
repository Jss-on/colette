"""Feedback learning — store approval decisions for calibration (FR-HIL-004)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from colette.schemas.common import ApprovalStatus, ApprovalTier


@dataclass(frozen=True)
class FeedbackRecord:
    """Immutable record of a predicted-vs-actual approval outcome."""

    request_id: str
    predicted_confidence: float
    actual_decision: ApprovalStatus
    tier: ApprovalTier
    stage: str
    timestamp: datetime


def compute_calibration_drift(records: list[FeedbackRecord]) -> float:
    """Calculate the gap between predicted and actual approval rates.

    Returns the absolute difference as a float in [0, 1].
    """
    if not records:
        return 0.0

    predicted_approve_rate = sum(1 for r in records if r.predicted_confidence >= 0.85) / len(
        records
    )
    approved = (ApprovalStatus.APPROVED, ApprovalStatus.AUTO_APPROVED)
    actual_approve_rate = sum(1 for r in records if r.actual_decision in approved) / len(records)

    return abs(predicted_approve_rate - actual_approve_rate)


async def store_feedback(record: FeedbackRecord, memory_manager: Any) -> None:
    """Persist a feedback record via the memory manager facade.

    The ``memory_manager`` argument is typed as ``Any`` to avoid hard
    coupling to the memory layer; Phase 4 will tighten this.
    """
    if memory_manager is None:
        return
    data = {
        "request_id": record.request_id,
        "predicted_confidence": record.predicted_confidence,
        "actual_decision": record.actual_decision.value,
        "tier": record.tier.value,
        "stage": record.stage,
        "timestamp": record.timestamp.isoformat(),
    }
    await memory_manager.store("feedback", data)


def create_feedback_record(
    request_id: str,
    predicted_confidence: float,
    actual_decision: ApprovalStatus,
    tier: ApprovalTier,
    stage: str,
) -> FeedbackRecord:
    """Convenience factory for ``FeedbackRecord``."""
    return FeedbackRecord(
        request_id=request_id,
        predicted_confidence=predicted_confidence,
        actual_decision=actual_decision,
        tier=tier,
        stage=stage,
        timestamp=datetime.now(UTC),
    )

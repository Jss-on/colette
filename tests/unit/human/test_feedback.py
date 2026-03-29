"""Tests for feedback learning."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from colette.human.feedback import (
    FeedbackRecord,
    compute_calibration_drift,
    create_feedback_record,
    store_feedback,
)
from colette.schemas.common import ApprovalStatus, ApprovalTier


class TestComputeCalibrationDrift:
    def test_empty_records(self) -> None:
        assert compute_calibration_drift([]) == 0.0

    def test_perfect_calibration(self) -> None:
        records = [
            FeedbackRecord(
                request_id="r1",
                predicted_confidence=0.90,
                actual_decision=ApprovalStatus.APPROVED,
                tier=ApprovalTier.T2_MODERATE,
                stage="design",
                timestamp=datetime.now(UTC),
            ),
            FeedbackRecord(
                request_id="r2",
                predicted_confidence=0.50,
                actual_decision=ApprovalStatus.REJECTED,
                tier=ApprovalTier.T2_MODERATE,
                stage="design",
                timestamp=datetime.now(UTC),
            ),
        ]
        drift = compute_calibration_drift(records)
        assert drift == 0.0

    def test_drift_with_mismatch(self) -> None:
        records = [
            FeedbackRecord(
                request_id="r1",
                predicted_confidence=0.90,
                actual_decision=ApprovalStatus.REJECTED,
                tier=ApprovalTier.T2_MODERATE,
                stage="testing",
                timestamp=datetime.now(UTC),
            ),
        ]
        drift = compute_calibration_drift(records)
        assert drift == 1.0  # predicted 100% approval, actual 0%


class TestCreateFeedbackRecord:
    def test_creates_record(self) -> None:
        record = create_feedback_record(
            "r1", 0.80, ApprovalStatus.APPROVED, ApprovalTier.T1_HIGH, "design"
        )
        assert record.request_id == "r1"
        assert record.predicted_confidence == 0.80


class TestStoreFeedback:
    @pytest.mark.asyncio
    async def test_noop_with_none_manager(self) -> None:
        record = create_feedback_record(
            "r1", 0.80, ApprovalStatus.APPROVED, ApprovalTier.T1_HIGH, "design"
        )
        # Should not raise
        await store_feedback(record, None)

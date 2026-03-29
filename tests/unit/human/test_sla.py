"""Tests for SLA tracking."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from colette.config import Settings
from colette.human.sla import SLARecord, build_sla_report, check_breach, compute_deadline
from colette.schemas.common import ApprovalTier


@pytest.fixture
def settings() -> Settings:
    return Settings()


class TestComputeDeadline:
    def test_t0_one_hour(self, settings: Settings) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        deadline = compute_deadline(ApprovalTier.T0_CRITICAL, now, settings)
        assert deadline == now + timedelta(hours=1)

    def test_t1_four_hours(self, settings: Settings) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        deadline = compute_deadline(ApprovalTier.T1_HIGH, now, settings)
        assert deadline == now + timedelta(hours=4)

    def test_t3_no_sla(self, settings: Settings) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        deadline = compute_deadline(ApprovalTier.T3_ROUTINE, now, settings)
        assert deadline.year == 9999


class TestCheckBreach:
    def test_not_breached_before_deadline(self) -> None:
        record = SLARecord(
            request_id="r1",
            tier=ApprovalTier.T0_CRITICAL,
            deadline=datetime.now(UTC) + timedelta(hours=1),
            created_at=datetime.now(UTC),
        )
        checked = check_breach(record)
        assert checked.breached is False

    def test_breached_after_deadline(self) -> None:
        record = SLARecord(
            request_id="r1",
            tier=ApprovalTier.T0_CRITICAL,
            deadline=datetime.now(UTC) - timedelta(hours=1),
            created_at=datetime.now(UTC) - timedelta(hours=2),
        )
        checked = check_breach(record)
        assert checked.breached is True

    def test_resolved_record_not_checked(self) -> None:
        record = SLARecord(
            request_id="r1",
            tier=ApprovalTier.T0_CRITICAL,
            deadline=datetime.now(UTC) - timedelta(hours=1),
            created_at=datetime.now(UTC) - timedelta(hours=2),
            resolved_at=datetime.now(UTC),
        )
        checked = check_breach(record)
        assert checked.breached is False


class TestBuildSlaReport:
    def test_empty_records(self) -> None:
        report = build_sla_report([])
        assert report["total"] == 0
        assert report["compliance_rate"] == 1.0

    def test_all_compliant(self) -> None:
        now = datetime.now(UTC)
        records = [
            SLARecord(
                request_id="r1",
                tier=ApprovalTier.T0_CRITICAL,
                deadline=now + timedelta(hours=1),
                created_at=now,
                resolved_at=now + timedelta(minutes=30),
            ),
        ]
        report = build_sla_report(records)
        assert report["breached"] == 0
        assert report["compliance_rate"] == 1.0

    def test_breach_reduces_compliance(self) -> None:
        now = datetime.now(UTC)
        records = [
            SLARecord(
                request_id="r1",
                tier=ApprovalTier.T0_CRITICAL,
                deadline=now,
                created_at=now,
                breached=True,
            ),
            SLARecord(
                request_id="r2",
                tier=ApprovalTier.T1_HIGH,
                deadline=now + timedelta(hours=4),
                created_at=now,
            ),
        ]
        report = build_sla_report(records)
        assert report["breached"] == 1
        assert report["compliance_rate"] == 0.5

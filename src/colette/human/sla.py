"""SLA tracking for human approvals (FR-HIL-006)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from colette.config import Settings
from colette.schemas.common import ApprovalTier

# Far-future sentinel for tiers without an SLA.
_NO_SLA = datetime(9999, 12, 31, tzinfo=UTC)


@dataclass(frozen=True)
class SLARecord:
    """Immutable record tracking a single approval SLA."""

    request_id: str
    tier: ApprovalTier
    deadline: datetime
    created_at: datetime
    resolved_at: datetime | None = None
    breached: bool = False


def compute_deadline(
    tier: ApprovalTier,
    created_at: datetime,
    settings: Settings,
) -> datetime:
    """Return the SLA deadline for *tier* starting at *created_at*."""
    if tier == ApprovalTier.T0_CRITICAL:
        return created_at + timedelta(seconds=settings.hil_t0_sla_seconds)
    if tier == ApprovalTier.T1_HIGH:
        return created_at + timedelta(seconds=settings.hil_t1_sla_seconds)
    # T2/T3 have no SLA
    return _NO_SLA


def check_breach(record: SLARecord) -> SLARecord:
    """Return a new ``SLARecord`` with ``breached`` set if the deadline has passed."""
    if record.resolved_at is not None:
        return record
    now = datetime.now(UTC)
    if now > record.deadline:
        return SLARecord(
            request_id=record.request_id,
            tier=record.tier,
            deadline=record.deadline,
            created_at=record.created_at,
            resolved_at=record.resolved_at,
            breached=True,
        )
    return record


def build_sla_report(records: list[SLARecord]) -> dict[str, Any]:
    """Compute SLA compliance metrics from a list of records."""
    if not records:
        return {"total": 0, "breached": 0, "compliance_rate": 1.0, "avg_resolution_seconds": 0.0}

    breached = sum(1 for r in records if r.breached)
    resolved = [r for r in records if r.resolved_at is not None]
    avg_resolution = 0.0
    if resolved:
        deltas = [
            (r.resolved_at - r.created_at).total_seconds() for r in resolved if r.resolved_at
        ]
        avg_resolution = sum(deltas) / len(deltas)

    return {
        "total": len(records),
        "breached": breached,
        "compliance_rate": 1.0 - (breached / len(records)),
        "avg_resolution_seconds": avg_resolution,
    }

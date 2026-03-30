"""Quality metrics dashboard data models (NFR-OBS-004).

Provides frozen Pydantic models for dashboard metric series and a builder
function that computes quality metrics from pipeline execution records.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from pydantic import BaseModel

logger = structlog.get_logger(__name__)


# ── Data models ────────────────────────────────────────────────────────


class MetricPoint(BaseModel, frozen=True):
    """A single timestamped metric value.

    Attributes:
        timestamp: ISO-8601 timestamp string.
        value: Numeric metric value.
    """

    timestamp: str
    value: float


class MetricSeries(BaseModel, frozen=True):
    """A named time-series of metric data points.

    Attributes:
        name: Metric identifier (e.g. ``"pipeline_completion_rate"``).
        unit: Unit of measurement (e.g. ``"ratio"``, ``"ms"``, ``"USD"``).
        points: Ordered list of timestamped values.
    """

    name: str
    unit: str
    points: list[MetricPoint]


class QualityDashboard(BaseModel, frozen=True):
    """Snapshot of quality metrics for a project.

    Attributes:
        project_id: Project identifier.
        generated_at: ISO-8601 timestamp when the dashboard was generated.
        metrics: Metric series keyed by canonical metric name.
    """

    project_id: str
    generated_at: str
    metrics: dict[str, MetricSeries]


# ── Metric keys ────────────────────────────────────────────────────────

_METRIC_KEYS = (
    "pipeline_completion_rate",
    "stage_latency_p50",
    "stage_latency_p99",
    "agent_success_rate",
    "escalation_frequency",
    "cost_trend",
    "hallucination_rate",
)


# ── Builder ────────────────────────────────────────────────────────────


def _percentile(values: list[float], pct: float) -> float:
    """Compute a percentile from a sorted list of values.

    Args:
        values: Sorted list of numeric values.
        pct: Percentile to compute (0.0 -- 1.0).

    Returns:
        The interpolated percentile value, or ``0.0`` for empty input.
    """
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * pct
    lower = int(k)
    upper = lower + 1
    if upper >= len(sorted_vals):
        return sorted_vals[lower]
    weight = k - lower
    return sorted_vals[lower] * (1.0 - weight) + sorted_vals[upper] * weight


def build_dashboard(
    project_id: str,
    *,
    pipeline_records: list[dict[str, Any]],
) -> QualityDashboard:
    """Build a quality dashboard from pipeline execution records.

    Each record is expected to be a dict containing:

    - ``stage`` (str): Pipeline stage name.
    - ``duration_ms`` (float): Stage execution duration in milliseconds.
    - ``outcome`` (str): ``"success"`` or ``"failure"``.
    - ``cost`` (float): USD cost for the record.
    - ``tokens`` (int): Total tokens consumed.
    - ``escalated`` (bool): Whether the record was escalated.
    - ``hallucination_detected`` (bool): Whether a hallucination was flagged.

    Args:
        project_id: Project identifier.
        pipeline_records: List of execution record dicts.

    Returns:
        A frozen :class:`QualityDashboard` with computed metric series.
    """
    now = datetime.now(tz=UTC).isoformat()
    total = len(pipeline_records)

    if total == 0:
        logger.warning("build_dashboard_empty_records", project_id=project_id)
        empty_metrics = {
            key: MetricSeries(name=key, unit="n/a", points=[]) for key in _METRIC_KEYS
        }
        return QualityDashboard(
            project_id=project_id,
            generated_at=now,
            metrics=empty_metrics,
        )

    # Collect raw values
    succeeded = 0
    escalated_count = 0
    hallucination_count = 0
    durations: list[float] = []
    cost_points: list[MetricPoint] = []
    success_points: list[MetricPoint] = []

    for rec in pipeline_records:
        ts = rec.get("timestamp", now)
        outcome = rec.get("outcome", "failure")
        duration_ms = float(rec.get("duration_ms", 0.0))
        cost = float(rec.get("cost", 0.0))
        is_escalated = bool(rec.get("escalated", False))
        has_hallucination = bool(rec.get("hallucination_detected", False))

        if outcome == "success":
            succeeded += 1
        if is_escalated:
            escalated_count += 1
        if has_hallucination:
            hallucination_count += 1

        durations.append(duration_ms)
        cost_points.append(MetricPoint(timestamp=ts, value=cost))
        success_points.append(
            MetricPoint(timestamp=ts, value=1.0 if outcome == "success" else 0.0)
        )

    # Compute aggregate metrics
    completion_rate = succeeded / total
    escalation_freq = escalated_count / total
    hallucination_rate = hallucination_count / total
    latency_p50 = _percentile(durations, 0.50)
    latency_p99 = _percentile(durations, 0.99)

    metrics: dict[str, MetricSeries] = {
        "pipeline_completion_rate": MetricSeries(
            name="pipeline_completion_rate",
            unit="ratio",
            points=[MetricPoint(timestamp=now, value=completion_rate)],
        ),
        "stage_latency_p50": MetricSeries(
            name="stage_latency_p50",
            unit="ms",
            points=[MetricPoint(timestamp=now, value=latency_p50)],
        ),
        "stage_latency_p99": MetricSeries(
            name="stage_latency_p99",
            unit="ms",
            points=[MetricPoint(timestamp=now, value=latency_p99)],
        ),
        "agent_success_rate": MetricSeries(
            name="agent_success_rate",
            unit="ratio",
            points=success_points,
        ),
        "escalation_frequency": MetricSeries(
            name="escalation_frequency",
            unit="ratio",
            points=[MetricPoint(timestamp=now, value=escalation_freq)],
        ),
        "cost_trend": MetricSeries(
            name="cost_trend",
            unit="USD",
            points=cost_points,
        ),
        "hallucination_rate": MetricSeries(
            name="hallucination_rate",
            unit="ratio",
            points=[MetricPoint(timestamp=now, value=hallucination_rate)],
        ),
    }

    logger.info(
        "dashboard_built",
        project_id=project_id,
        record_count=total,
        completion_rate=round(completion_rate, 4),
        latency_p50=round(latency_p50, 2),
        latency_p99=round(latency_p99, 2),
    )

    return QualityDashboard(
        project_id=project_id,
        generated_at=now,
        metrics=metrics,
    )

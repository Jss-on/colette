"""Regression and cost alerting (NFR-OBS-003, NFR-OBS-005).

Defines alert models, predefined alert rules, and evaluation functions
that detect metric regressions and threshold violations.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


# ── Enums ──────────────────────────────────────────────────────────────


class AlertSeverity(StrEnum):
    """Severity level for observability alerts.

    Attributes:
        CRITICAL: System-breaking or data-loss risk — immediate action required.
        HIGH: Significant degradation — should be addressed urgently.
        MEDIUM: Notable regression — investigate when possible.
        LOW: Minor deviation — informational.
        INFO: Purely informational, no action needed.
    """

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


# ── Data models ────────────────────────────────────────────────────────


class Alert(BaseModel, frozen=True):
    """Immutable alert raised when a metric violates a threshold.

    Attributes:
        alert_id: Unique identifier (UUID4).
        severity: Alert severity level.
        category: Alert category (e.g. ``"regression"``, ``"threshold"``).
        message: Human-readable description of the alert.
        metric_name: Name of the metric that triggered the alert.
        current_value: Observed metric value.
        threshold_value: Threshold that was violated.
        created_at: ISO-8601 timestamp of alert creation.
    """

    alert_id: str = Field(default_factory=lambda: str(uuid4()))
    severity: AlertSeverity
    category: str
    message: str
    metric_name: str
    current_value: float
    threshold_value: float
    created_at: str = Field(
        default_factory=lambda: (
            __import__("datetime").datetime.now(tz=__import__("datetime").timezone.utc).isoformat()
        )
    )


class AlertRule(BaseModel, frozen=True):
    """A declarative rule that maps a metric condition to an alert.

    Attributes:
        name: Human-readable rule name.
        metric_name: Metric this rule evaluates.
        condition: Comparison operator — ``"gt"`` (greater than) or ``"lt"`` (less than).
        threshold: Threshold value for the condition.
        severity: Alert severity to assign when the rule fires.
    """

    name: str
    metric_name: str
    condition: str  # "gt" or "lt"
    threshold: float
    severity: AlertSeverity


# ── Default rules ──────────────────────────────────────────────────────

DEFAULT_ALERT_RULES: tuple[AlertRule, ...] = (
    AlertRule(
        name="low_agent_success_rate",
        metric_name="agent_success_rate",
        condition="lt",
        threshold=0.90,
        severity=AlertSeverity.HIGH,
    ),
    AlertRule(
        name="low_pipeline_completion_rate",
        metric_name="pipeline_completion_rate",
        condition="lt",
        threshold=0.80,
        severity=AlertSeverity.CRITICAL,
    ),
    AlertRule(
        name="high_cost_overrun_ratio",
        metric_name="cost_overrun_ratio",
        condition="gt",
        threshold=2.0,
        severity=AlertSeverity.HIGH,
    ),
    AlertRule(
        name="high_escalation_rate",
        metric_name="escalation_rate",
        condition="gt",
        threshold=0.30,
        severity=AlertSeverity.MEDIUM,
    ),
)


# ── Evaluation functions ───────────────────────────────────────────────


def check_regression(
    metric_name: str,
    current_value: float,
    baseline_value: float,
    *,
    threshold_pct: float = 10.0,
) -> Alert | None:
    """Check whether a metric has regressed from its baseline.

    A regression is detected when ``current_value`` has dropped by more
    than ``threshold_pct`` percent relative to ``baseline_value``.

    Args:
        metric_name: Name of the metric being evaluated.
        current_value: Current observed value.
        baseline_value: Previous baseline value.
        threshold_pct: Percentage drop that constitutes a regression (default 10%).

    Returns:
        An :class:`Alert` if regression detected, else ``None``.
    """
    if baseline_value == 0.0:
        return None

    drop_pct = ((baseline_value - current_value) / abs(baseline_value)) * 100.0

    if drop_pct > threshold_pct:
        alert = Alert(
            severity=AlertSeverity.HIGH,
            category="regression",
            message=(
                f"Metric '{metric_name}' regressed by {drop_pct:.1f}% "
                f"(baseline={baseline_value:.4f}, current={current_value:.4f}, "
                f"threshold={threshold_pct:.1f}%)"
            ),
            metric_name=metric_name,
            current_value=current_value,
            threshold_value=baseline_value * (1.0 - threshold_pct / 100.0),
        )
        logger.warning(
            "metric_regression_detected",
            metric_name=metric_name,
            current_value=current_value,
            baseline_value=baseline_value,
            drop_pct=round(drop_pct, 2),
        )
        return alert

    return None


def evaluate_rule(rule: AlertRule, current_value: float) -> Alert | None:
    """Evaluate a single alert rule against a current metric value.

    Args:
        rule: The alert rule to evaluate.
        current_value: Current observed metric value.

    Returns:
        An :class:`Alert` if the rule condition is violated, else ``None``.
    """
    triggered = (rule.condition == "gt" and current_value > rule.threshold) or (
        rule.condition == "lt" and current_value < rule.threshold
    )

    if triggered:
        alert = Alert(
            severity=rule.severity,
            category="threshold",
            message=(
                f"Rule '{rule.name}' triggered: {rule.metric_name}="
                f"{current_value:.4f} {rule.condition} {rule.threshold:.4f}"
            ),
            metric_name=rule.metric_name,
            current_value=current_value,
            threshold_value=rule.threshold,
        )
        logger.warning(
            "alert_rule_triggered",
            rule_name=rule.name,
            metric_name=rule.metric_name,
            current_value=current_value,
            condition=rule.condition,
            threshold=rule.threshold,
        )
        return alert

    return None

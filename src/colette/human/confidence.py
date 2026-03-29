"""Confidence scoring and escalation rules (FR-HIL-002)."""

from __future__ import annotations

from typing import Any

from colette.config import Settings
from colette.human.models import ConfidenceResult


def evaluate_confidence(score: float, settings: Settings) -> ConfidenceResult:
    """Classify a confidence score into an action.

    - < threshold (0.60): escalate immediately
    - < flag_threshold (0.85): flag for human review
    - >= flag_threshold: auto-approve
    """
    if score < settings.hil_confidence_threshold:
        return ConfidenceResult(
            score=score,
            action="escalate",
            reasoning=f"Confidence {score:.2f} below escalation threshold "
            f"{settings.hil_confidence_threshold}",
        )
    if score < settings.hil_confidence_flag_threshold:
        return ConfidenceResult(
            score=score,
            action="flag_for_review",
            reasoning=f"Confidence {score:.2f} between "
            f"{settings.hil_confidence_threshold} and "
            f"{settings.hil_confidence_flag_threshold}",
        )
    return ConfidenceResult(
        score=score,
        action="auto_approve",
        reasoning=f"Confidence {score:.2f} meets auto-approve threshold "
        f"{settings.hil_confidence_flag_threshold}",
    )


def extract_confidence_from_response(response: dict[str, Any]) -> float:
    """Extract a confidence score from an LLM structured output.

    Returns 0.50 (triggers review) if the field is missing or malformed.
    """
    raw = response.get("confidence", response.get("confidence_score"))
    if raw is None:
        return 0.50
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.50
    return max(0.0, min(1.0, value))

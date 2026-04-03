"""Rework routing logic — maps gate failures to rework targets (Phase 1)."""

from __future__ import annotations

import structlog

from colette.config import Settings
from colette.schemas.common import QualityGateResult
from colette.schemas.rework import ReworkDecision, ReworkDirective

logger = structlog.get_logger()

# Keywords indicating the root cause is upstream (scope/requirements/design).
_UPSTREAM_KEYWORDS: frozenset[str] = frozenset(
    {
        "scope",
        "requirement",
        "missing requirement",
        "ambiguous",
        "undefined",
        "underspecified",
        "incomplete spec",
        "architecture",
        "design flaw",
        "schema mismatch",
        "contract",
        "interface",
    }
)

# Default rework target mapping per gate.
_DEFAULT_REWORK_TARGETS: dict[str, dict[str, str]] = {
    "requirements": {
        "self": "requirements",
    },
    "design": {
        "self": "design",
        "upstream": "requirements",
    },
    "implementation": {
        "self": "implementation",
        "upstream": "design",
    },
    "testing": {
        "self": "implementation",
        "upstream": "design",
    },
    "staging": {
        "self": "testing",
        "upstream": "implementation",
    },
}


def classify_failure(reasons: list[str]) -> str:
    """Classify failure reasons as 'upstream' or 'self'.

    Uses keyword matching against the concatenated failure text.
    """
    combined = " ".join(reasons).lower()
    for keyword in _UPSTREAM_KEYWORDS:
        if keyword in combined:
            return "upstream"
    return "self"


class ReworkRouter:
    """Determines rework decisions from gate evaluation results."""

    def __init__(self, settings: Settings) -> None:
        self._max_stage_attempts = settings.max_stage_rework_attempts
        self._max_total = settings.max_pipeline_rework_total

    def decide(
        self,
        gate_result: QualityGateResult,
        rework_count: dict[str, int],
    ) -> tuple[ReworkDecision, ReworkDirective | None]:
        """Return a ``(decision, directive)`` pair for the given gate result.

        When the gate passes, returns ``(PASS, None)``.
        When rework budgets are exhausted, returns ``(PASS, None)`` with a
        degraded-quality warning logged.
        """
        if gate_result.passed:
            return ReworkDecision.PASS, None

        gate_name = gate_result.gate_name
        targets = _DEFAULT_REWORK_TARGETS.get(gate_name, {"self": gate_name})

        # Determine target stage.
        classification = classify_failure(gate_result.failure_reasons)
        target_stage = targets.get(classification, targets.get("self", gate_name))

        # Budget checks.
        stage_attempts = rework_count.get(target_stage, 0)
        total_attempts = sum(rework_count.values())

        if stage_attempts >= self._max_stage_attempts:
            logger.warning(
                "rework.budget_exhausted_stage",
                gate=gate_name,
                target=target_stage,
                attempts=stage_attempts,
            )
            return ReworkDecision.PASS, None

        if total_attempts >= self._max_total:
            logger.warning(
                "rework.budget_exhausted_total",
                gate=gate_name,
                total=total_attempts,
            )
            return ReworkDecision.PASS, None

        # Build directive.
        decision = (
            ReworkDecision.REWORK_SELF
            if target_stage == targets.get("self", gate_name)
            else ReworkDecision.REWORK_TARGET
        )

        directive = ReworkDirective(
            source_gate=gate_name,
            target_stage=target_stage,
            failure_reasons=list(gate_result.failure_reasons),
            attempt_number=stage_attempts + 1,
            max_attempts=self._max_stage_attempts,
        )

        logger.info(
            "rework.routed",
            gate=gate_name,
            decision=decision.value,
            target=target_stage,
            attempt=directive.attempt_number,
        )

        return decision, directive

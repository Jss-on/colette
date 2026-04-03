"""Deployment staging quality gate (Section 12)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from colette.orchestrator.rework_router import classify_failure
from colette.schemas.common import QualityGateResult, StageName


class StagingGate:
    """Staging deployment targets present with health-check URLs."""

    @property
    def name(self) -> str:
        return "staging"

    async def evaluate(self, state: dict[str, Any]) -> QualityGateResult:
        handoff = state.get("handoffs", {}).get(StageName.DEPLOYMENT.value, {})
        criteria: dict[str, bool] = {}
        failures: list[str] = []

        # Deployment targets present
        targets = handoff.get("targets", [])
        criteria["targets_present"] = len(targets) > 0
        if not criteria["targets_present"]:
            failures.append("No deployment targets defined")

        # Health check URLs defined
        has_health = any(t.get("health_check_url") for t in targets)
        criteria["health_checks_defined"] = has_health
        if not criteria["health_checks_defined"]:
            failures.append("No health check URLs defined")

        # Rollback command present
        rollback = handoff.get("rollback_command", "")
        criteria["rollback_command_present"] = bool(rollback)
        if not criteria["rollback_command_present"]:
            failures.append("Rollback command not specified")

        # SLO targets defined
        slos = handoff.get("slo_targets", {})
        criteria["slo_targets_defined"] = len(slos) > 0
        if not criteria["slo_targets_defined"]:
            failures.append("No SLO targets defined")

        passed = all(criteria.values())

        rework_decision = "pass"
        rework_target: str | None = None
        if not passed:
            classification = classify_failure(failures)
            if classification == "upstream":
                rework_decision = "rework_target"
                rework_target = "implementation"
            else:
                rework_decision = "rework_target"
                rework_target = "testing"

        return QualityGateResult(
            gate_name=self.name,
            passed=passed,
            score=1.0 if passed else sum(criteria.values()) / max(len(criteria), 1),
            criteria_results=criteria,
            failure_reasons=failures,
            evaluated_at=datetime.now(UTC),
            rework_decision=rework_decision,
            rework_target_stage=rework_target,
        )

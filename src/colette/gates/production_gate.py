"""Production deployment quality gate (Section 12, FR-HIL-001 T0)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from colette.schemas.common import QualityGateResult


class ProductionGate:
    """Staging gate must have passed; requires human T0 approval."""

    @property
    def name(self) -> str:
        return "production"

    async def evaluate(self, state: dict[str, Any]) -> QualityGateResult:
        criteria: dict[str, bool] = {}
        failures: list[str] = []

        # Staging gate must have passed first
        staging_result = state.get("quality_gate_results", {}).get("staging", {})
        criteria["staging_gate_passed"] = bool(staging_result.get("passed", False))
        if not criteria["staging_gate_passed"]:
            failures.append("Staging gate has not passed")

        # Human approval required (check approval decisions for production)
        decisions = state.get("approval_decisions", [])
        prod_approvals = [
            d
            for d in decisions
            if d.get("stage") == "production" and d.get("status") == "approved"
        ]
        criteria["human_approval_received"] = len(prod_approvals) > 0
        if not criteria["human_approval_received"]:
            failures.append("Human approval for production not received")

        passed = all(criteria.values())
        return QualityGateResult(
            gate_name=self.name,
            passed=passed,
            score=1.0 if passed else 0.0,
            criteria_results=criteria,
            failure_reasons=failures,
            evaluated_at=datetime.now(UTC),
        )

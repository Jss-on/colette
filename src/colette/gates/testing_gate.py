"""Testing → Deployment quality gate (Section 12)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from colette.schemas.common import QualityGateResult, StageName


class TestingGate:
    """Coverage >= 80/70, no HIGH/CRIT security findings, contract tests pass, readiness >= 75."""

    @property
    def name(self) -> str:
        return "testing"

    async def evaluate(self, state: dict[str, Any]) -> QualityGateResult:
        handoff = state.get("handoffs", {}).get(StageName.TESTING.value, {})
        criteria: dict[str, bool] = {}
        failures: list[str] = []

        # Line coverage >= 80%
        line_cov = handoff.get("overall_line_coverage", 0.0)
        criteria["line_coverage_ge_80"] = line_cov >= 80.0
        if not criteria["line_coverage_ge_80"]:
            failures.append(f"Line coverage {line_cov:.1f}% < 80%")

        # Branch coverage >= 70%
        branch_cov = handoff.get("overall_branch_coverage", 0.0)
        criteria["branch_coverage_ge_70"] = branch_cov >= 70.0
        if not criteria["branch_coverage_ge_70"]:
            failures.append(f"Branch coverage {branch_cov:.1f}% < 70%")

        # No HIGH/CRITICAL security findings
        findings = handoff.get("security_findings", [])
        blocking = [f for f in findings if f.get("severity") in ("CRITICAL", "HIGH")]
        criteria["no_blocking_security_findings"] = len(blocking) == 0
        if not criteria["no_blocking_security_findings"]:
            failures.append(f"{len(blocking)} HIGH/CRITICAL security finding(s)")

        # Contract tests passed
        criteria["contract_tests_passed"] = bool(handoff.get("contract_tests_passed", False))
        if not criteria["contract_tests_passed"]:
            failures.append("Contract tests did not pass")

        # Deploy readiness >= 75
        readiness = handoff.get("deploy_readiness_score", 0)
        criteria["deploy_readiness_ge_75"] = readiness >= 75
        if not criteria["deploy_readiness_ge_75"]:
            failures.append(f"Deploy readiness {readiness} < 75")

        passed = all(criteria.values())
        return QualityGateResult(
            gate_name=self.name,
            passed=passed,
            score=readiness / 100.0,
            criteria_results=criteria,
            failure_reasons=failures,
            evaluated_at=datetime.now(UTC),
        )

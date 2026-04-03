"""Testing → Deployment quality gate (Section 12)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from colette.schemas.common import QualityGateResult, StageName

if TYPE_CHECKING:
    from colette.config import Settings


class TestingGate:
    """Coverage >= 80/70, no HIGH/CRIT security findings, contract tests pass, readiness >= 75.

    All thresholds are configurable via ``Settings`` (env vars with ``COLETTE_GATE_`` prefix).
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings

    @property
    def name(self) -> str:
        return "testing"

    def _threshold(self, attr: str, default: float | int) -> float | int:
        if self._settings is not None:
            return getattr(self._settings, attr, default)  # type: ignore[no-any-return]
        return default

    async def evaluate(self, state: dict[str, Any]) -> QualityGateResult:
        handoff = state.get("handoffs", {}).get(StageName.TESTING.value, {})
        criteria: dict[str, bool] = {}
        failures: list[str] = []

        min_line = self._threshold("gate_min_line_coverage", 80.0)
        min_branch = self._threshold("gate_min_branch_coverage", 70.0)
        max_blocking = self._threshold("gate_max_blocking_security_findings", 0)
        min_readiness = self._threshold("gate_min_deploy_readiness", 75)

        # Line coverage
        line_cov = handoff.get("overall_line_coverage", 0.0)
        criteria["line_coverage_ge_80"] = line_cov >= min_line
        if not criteria["line_coverage_ge_80"]:
            failures.append(f"Line coverage {line_cov:.1f}% < {min_line}%")

        # Branch coverage
        branch_cov = handoff.get("overall_branch_coverage", 0.0)
        criteria["branch_coverage_ge_70"] = branch_cov >= min_branch
        if not criteria["branch_coverage_ge_70"]:
            failures.append(f"Branch coverage {branch_cov:.1f}% < {min_branch}%")

        # No HIGH/CRITICAL security findings (beyond allowed threshold)
        findings = handoff.get("security_findings", [])
        blocking = [f for f in findings if f.get("severity") in ("CRITICAL", "HIGH")]
        criteria["no_blocking_security_findings"] = len(blocking) <= max_blocking
        if not criteria["no_blocking_security_findings"]:
            failures.append(f"{len(blocking)} HIGH/CRITICAL security finding(s)")

        # Contract tests passed
        criteria["contract_tests_passed"] = bool(handoff.get("contract_tests_passed", False))
        if not criteria["contract_tests_passed"]:
            failures.append("Contract tests did not pass")

        # Deploy readiness
        readiness = handoff.get("deploy_readiness_score", 0)
        criteria["deploy_readiness_ge_75"] = readiness >= min_readiness
        if not criteria["deploy_readiness_ge_75"]:
            failures.append(f"Deploy readiness {readiness} < {min_readiness}")

        passed = all(criteria.values())
        return QualityGateResult(
            gate_name=self.name,
            passed=passed,
            score=readiness / 100.0,
            criteria_results=criteria,
            failure_reasons=failures,
            evaluated_at=datetime.now(UTC),
        )

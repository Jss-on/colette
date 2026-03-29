"""Implementation → Testing quality gate (Section 12)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from colette.schemas.common import QualityGateResult, StageName


class ImplementationGate:
    """Lint, type-check, and build must pass; files changed; git ref present."""

    @property
    def name(self) -> str:
        return "implementation"

    async def evaluate(self, state: dict[str, Any]) -> QualityGateResult:
        handoff = state.get("handoffs", {}).get(StageName.IMPLEMENTATION.value, {})
        criteria: dict[str, bool] = {}
        failures: list[str] = []

        for check in ("lint_passed", "type_check_passed", "build_passed"):
            criteria[check] = bool(handoff.get(check, False))
            if not criteria[check]:
                failures.append(f"{check} is False")

        files = handoff.get("files_changed", [])
        criteria["files_changed_non_empty"] = len(files) > 0
        if not criteria["files_changed_non_empty"]:
            failures.append("No files changed")

        git_ref = handoff.get("git_ref", "")
        criteria["git_ref_present"] = bool(git_ref)
        if not criteria["git_ref_present"]:
            failures.append("Git ref missing")

        passed = all(criteria.values())
        return QualityGateResult(
            gate_name=self.name,
            passed=passed,
            score=1.0 if passed else sum(criteria.values()) / max(len(criteria), 1),
            criteria_results=criteria,
            failure_reasons=failures,
            evaluated_at=datetime.now(UTC),
        )

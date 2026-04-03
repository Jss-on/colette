"""Implementation → Testing quality gate (Section 12)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from colette.orchestrator.rework_router import classify_failure
from colette.schemas.common import QualityGateResult, StageName


class ImplementationGate:
    """Files changed must be non-empty; LLM verification is advisory."""

    @property
    def name(self) -> str:
        return "implementation"

    async def evaluate(self, state: dict[str, Any]) -> QualityGateResult:
        handoff = state.get("handoffs", {}).get(StageName.IMPLEMENTATION.value, {})
        criteria: dict[str, bool] = {}
        failures: list[str] = []
        warnings: list[str] = []

        # Hard requirements: files must exist.
        files = handoff.get("files_changed", [])
        criteria["files_changed_non_empty"] = len(files) > 0
        if not criteria["files_changed_non_empty"]:
            failures.append("No files changed")

        # Advisory: LLM-based verification flags are informational —
        # no actual linter/type-checker/build tool was run, so these
        # reflect an LLM opinion and should not block the gate.
        for check in ("lint_passed", "type_check_passed", "build_passed"):
            val = bool(handoff.get(check, False))
            criteria[check] = val
            if not val:
                warnings.append(f"{check} is False (advisory)")

        git_ref = handoff.get("git_ref", "")
        criteria["git_ref_present"] = bool(git_ref)
        if not criteria["git_ref_present"]:
            # Not a hard failure — generated code may not have a git ref.
            warnings.append("Git ref missing (advisory)")

        # Gate passes if files were generated (hard requirement).
        passed = criteria["files_changed_non_empty"]
        advisory_score = sum(criteria.values()) / max(len(criteria), 1)

        rework_decision = "pass"
        rework_target: str | None = None
        if not passed:
            all_reasons = failures + warnings
            classification = classify_failure(all_reasons)
            if classification == "upstream":
                rework_decision = "rework_target"
                rework_target = "design"
            else:
                rework_decision = "rework_self"
                rework_target = "implementation"

        return QualityGateResult(
            gate_name=self.name,
            passed=passed,
            score=advisory_score,
            criteria_results=criteria,
            failure_reasons=failures + warnings,
            evaluated_at=datetime.now(UTC),
            rework_decision=rework_decision,
            rework_target_stage=rework_target,
        )

"""Requirements → Design quality gate (Section 12)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from colette.schemas.common import QualityGateResult, StageName


class RequirementsGate:
    """PRD completeness >= 0.80, all stories have acceptance criteria."""

    @property
    def name(self) -> str:
        return "requirements"

    async def evaluate(self, state: dict[str, Any]) -> QualityGateResult:
        handoff = state.get("handoffs", {}).get(StageName.REQUIREMENTS.value, {})
        criteria: dict[str, bool] = {}
        failures: list[str] = []

        # Completeness score >= 0.80
        score = handoff.get("completeness_score", 0.0)
        criteria["completeness_score_ge_080"] = score >= 0.80
        if not criteria["completeness_score_ge_080"]:
            failures.append(f"Completeness score {score:.2f} < 0.80")

        # At least one functional requirement
        reqs = handoff.get("functional_requirements", [])
        criteria["has_functional_requirements"] = len(reqs) > 0
        if not criteria["has_functional_requirements"]:
            failures.append("No functional requirements defined")

        # All stories have acceptance criteria
        all_have_criteria = all(len(r.get("acceptance_criteria", [])) > 0 for r in reqs)
        criteria["all_stories_have_acceptance_criteria"] = all_have_criteria
        if not all_have_criteria:
            failures.append("Some user stories lack acceptance criteria")

        # No unresolved open questions (warning only — not blocking)
        open_qs = handoff.get("open_questions", [])
        criteria["no_open_questions"] = len(open_qs) == 0

        passed = all(
            criteria[k]
            for k in [
                "completeness_score_ge_080",
                "has_functional_requirements",
                "all_stories_have_acceptance_criteria",
            ]
        )

        return QualityGateResult(
            gate_name=self.name,
            passed=passed,
            score=score,
            criteria_results=criteria,
            failure_reasons=failures,
            evaluated_at=datetime.now(UTC),
        )

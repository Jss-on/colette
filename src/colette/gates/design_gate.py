"""Design → Implementation quality gate (Section 12)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from colette.orchestrator.rework_router import classify_failure
from colette.schemas.common import QualityGateResult, StageName


class DesignGate:
    """OpenAPI spec present, DB entities defined, ADRs present."""

    @property
    def name(self) -> str:
        return "design"

    async def evaluate(self, state: dict[str, Any]) -> QualityGateResult:
        handoff = state.get("handoffs", {}).get(StageName.DESIGN.value, {})
        criteria: dict[str, bool] = {}
        failures: list[str] = []

        # OpenAPI spec present and non-empty
        spec = handoff.get("openapi_spec", "")
        criteria["openapi_spec_present"] = bool(spec and len(spec) > 10)
        if not criteria["openapi_spec_present"]:
            failures.append("OpenAPI spec missing or empty")

        # Architecture summary present
        arch = handoff.get("architecture_summary", "")
        criteria["architecture_summary_present"] = bool(arch)
        if not criteria["architecture_summary_present"]:
            failures.append("Architecture summary missing")

        # Tech stack defined
        stack = handoff.get("tech_stack", {})
        criteria["tech_stack_defined"] = len(stack) > 0
        if not criteria["tech_stack_defined"]:
            failures.append("Tech stack not defined")

        # DB entities present
        entities = handoff.get("db_entities", [])
        criteria["db_entities_present"] = len(entities) > 0
        if not criteria["db_entities_present"]:
            failures.append("No database entities defined")

        passed = all(criteria.values())

        rework_decision = "pass"
        rework_target: str | None = None
        if not passed:
            classification = classify_failure(failures)
            if classification == "upstream":
                rework_decision = "rework_target"
                rework_target = "requirements"
            else:
                rework_decision = "rework_self"
                rework_target = "design"

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

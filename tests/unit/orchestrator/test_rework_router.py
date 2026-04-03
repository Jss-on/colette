"""Tests for rework router — failure classification and decision logic (Phase 1)."""

from __future__ import annotations

import pytest

from colette.config import Settings
from colette.orchestrator.rework_router import (
    ReworkRouter,
    classify_failure,
)
from colette.schemas.common import QualityGateResult
from colette.schemas.rework import ReworkDecision


@pytest.fixture
def settings() -> Settings:
    return Settings(
        max_stage_rework_attempts=3,
        max_pipeline_rework_total=10,
    )


@pytest.fixture
def router(settings: Settings) -> ReworkRouter:
    return ReworkRouter(settings)


class TestClassifyFailure:
    """Test failure classification (upstream vs self)."""

    def test_upstream_scope(self) -> None:
        assert classify_failure(["Missing requirement for API"]) == "upstream"

    def test_upstream_ambiguous(self) -> None:
        assert classify_failure(["Ambiguous specification"]) == "upstream"

    def test_upstream_design_flaw(self) -> None:
        assert classify_failure(["Design flaw in auth module"]) == "upstream"

    def test_upstream_schema_mismatch(self) -> None:
        assert classify_failure(["Schema mismatch between services"]) == "upstream"

    def test_self_quality(self) -> None:
        assert classify_failure(["Line coverage 60% < 80%"]) == "self"

    def test_self_no_files(self) -> None:
        assert classify_failure(["No files changed"]) == "self"

    def test_empty_reasons(self) -> None:
        assert classify_failure([]) == "self"

    def test_multiple_reasons_upstream_wins(self) -> None:
        reasons = [
            "Line coverage low",
            "Missing requirement for notifications",
        ]
        assert classify_failure(reasons) == "upstream"


class TestReworkRouter:
    """Test ReworkRouter decision logic."""

    def _make_result(
        self,
        gate_name: str,
        passed: bool,
        failure_reasons: list[str] | None = None,
        score: float = 0.5,
    ) -> QualityGateResult:
        return QualityGateResult(
            gate_name=gate_name,
            passed=passed,
            score=score,
            failure_reasons=failure_reasons or [],
        )

    def test_pass_on_gate_pass(self, router: ReworkRouter) -> None:
        result = self._make_result("requirements", passed=True)
        decision, directive = router.decide(result, {})
        assert decision == ReworkDecision.PASS
        assert directive is None

    def test_requirements_gate_rework_self(self, router: ReworkRouter) -> None:
        result = self._make_result(
            "requirements",
            passed=False,
            failure_reasons=["Completeness score 0.50 < 0.80"],
        )
        decision, directive = router.decide(result, {})
        assert decision == ReworkDecision.REWORK_SELF
        assert directive is not None
        assert directive.target_stage == "requirements"
        assert directive.attempt_number == 1

    def test_design_gate_rework_self(self, router: ReworkRouter) -> None:
        result = self._make_result(
            "design",
            passed=False,
            failure_reasons=["OpenAPI spec missing or empty"],
        )
        decision, directive = router.decide(result, {})
        assert decision == ReworkDecision.REWORK_SELF
        assert directive is not None
        assert directive.target_stage == "design"

    def test_design_gate_rework_upstream(self, router: ReworkRouter) -> None:
        result = self._make_result(
            "design",
            passed=False,
            failure_reasons=["Missing requirement for payment flow"],
        )
        decision, directive = router.decide(result, {})
        assert decision == ReworkDecision.REWORK_TARGET
        assert directive is not None
        assert directive.target_stage == "requirements"

    def test_testing_gate_rework_implementation(self, router: ReworkRouter) -> None:
        result = self._make_result(
            "testing",
            passed=False,
            failure_reasons=["Line coverage 50% < 80%"],
        )
        _, directive = router.decide(result, {})
        assert directive is not None
        assert directive.target_stage == "implementation"

    def test_testing_gate_rework_design(self, router: ReworkRouter) -> None:
        result = self._make_result(
            "testing",
            passed=False,
            failure_reasons=["Contract violation due to design flaw"],
        )
        _, directive = router.decide(result, {})
        assert directive is not None
        assert directive.target_stage == "design"

    def test_staging_gate_rework_testing(self, router: ReworkRouter) -> None:
        result = self._make_result(
            "staging",
            passed=False,
            failure_reasons=["No health check URLs defined"],
        )
        _, directive = router.decide(result, {})
        assert directive is not None
        assert directive.target_stage == "testing"

    def test_budget_exhausted_per_stage(self, router: ReworkRouter) -> None:
        result = self._make_result(
            "requirements",
            passed=False,
            failure_reasons=["Low completeness"],
        )
        rework_count = {"requirements": 3}
        decision, directive = router.decide(result, rework_count)
        assert decision == ReworkDecision.PASS
        assert directive is None

    def test_budget_exhausted_total(self, router: ReworkRouter) -> None:
        result = self._make_result(
            "requirements",
            passed=False,
            failure_reasons=["Low completeness"],
        )
        rework_count = {"design": 4, "implementation": 4, "testing": 2}
        decision, directive = router.decide(result, rework_count)
        assert decision == ReworkDecision.PASS
        assert directive is None

    def test_attempt_number_increments(self, router: ReworkRouter) -> None:
        result = self._make_result(
            "requirements",
            passed=False,
            failure_reasons=["Low completeness"],
        )
        rework_count = {"requirements": 2}
        _, directive = router.decide(result, rework_count)
        assert directive is not None
        assert directive.attempt_number == 3

    def test_directive_contains_failure_reasons(self, router: ReworkRouter) -> None:
        reasons = ["Coverage too low", "Missing tests"]
        result = self._make_result(
            "implementation",
            passed=False,
            failure_reasons=reasons,
        )
        _, directive = router.decide(result, {})
        assert directive is not None
        assert directive.failure_reasons == reasons

    def test_unknown_gate_defaults_to_self(self, router: ReworkRouter) -> None:
        result = self._make_result(
            "unknown_gate",
            passed=False,
            failure_reasons=["Something failed"],
        )
        _, directive = router.decide(result, {})
        assert directive is not None
        assert directive.target_stage == "unknown_gate"

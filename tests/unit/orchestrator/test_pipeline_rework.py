"""Tests for pipeline rework routing — backward edge logic (Phase 1)."""

from __future__ import annotations

from typing import Any

from colette.orchestrator.pipeline import _gate_router, _next_stage
from colette.orchestrator.state import STAGE_ORDER


class TestGateRouterRework:
    """Test _gate_router with rework decisions."""

    def _make_state(
        self,
        gate_name: str,
        *,
        passed: bool,
        rework_decision: str = "pass",
        rework_target_stage: str | None = None,
    ) -> dict[str, Any]:
        return {
            "quality_gate_results": {
                gate_name: {
                    "passed": passed,
                    "rework_decision": rework_decision,
                    "rework_target_stage": rework_target_stage,
                },
            },
            "skip_stages": [],
        }

    def test_pass_routes_forward(self) -> None:
        router = _gate_router("requirements", "requirements", [])
        state = self._make_state("requirements", passed=True)
        assert router(state) == "stage_design"

    def test_fail_without_rework_routes_to_gate_failed(self) -> None:
        router = _gate_router("requirements", "requirements", [])
        state = self._make_state("requirements", passed=False)
        assert router(state) == "gate_failed"

    def test_rework_self_routes_backward(self) -> None:
        router = _gate_router("requirements", "requirements", [])
        state = self._make_state(
            "requirements",
            passed=False,
            rework_decision="rework_self",
            rework_target_stage="requirements",
        )
        assert router(state) == "stage_requirements"

    def test_rework_target_routes_to_upstream(self) -> None:
        router = _gate_router("design", "design", [])
        state = self._make_state(
            "design",
            passed=False,
            rework_decision="rework_target",
            rework_target_stage="requirements",
        )
        assert router(state) == "stage_requirements"

    def test_testing_rework_to_implementation(self) -> None:
        router = _gate_router("testing", "testing", [])
        state = self._make_state(
            "testing",
            passed=False,
            rework_decision="rework_target",
            rework_target_stage="implementation",
        )
        assert router(state) == "stage_implementation"

    def test_staging_rework_to_testing(self) -> None:
        router = _gate_router("staging", "deployment", [])
        state = self._make_state(
            "staging",
            passed=False,
            rework_decision="rework_target",
            rework_target_stage="testing",
        )
        assert router(state) == "stage_testing"

    def test_pass_at_last_stage_routes_to_end(self) -> None:
        router = _gate_router("staging", "deployment", [])
        state = self._make_state("staging", passed=True)
        # deployment -> next is monitoring
        assert router(state) == "stage_monitoring"

    def test_rework_with_no_target_falls_to_gate_failed(self) -> None:
        router = _gate_router("design", "design", [])
        state = self._make_state(
            "design",
            passed=False,
            rework_decision="rework_target",
            rework_target_stage=None,
        )
        assert router(state) == "gate_failed"


class TestNextStage:
    """Test _next_stage helper."""

    def test_requirements_to_design(self) -> None:
        assert _next_stage("requirements", []) == "design"

    def test_deployment_to_monitoring(self) -> None:
        assert _next_stage("deployment", []) == "monitoring"

    def test_monitoring_is_last(self) -> None:
        assert _next_stage("monitoring", []) is None

    def test_skip_stages(self) -> None:
        assert _next_stage("requirements", ["design"]) == "implementation"

    def test_skip_all_remaining(self) -> None:
        remaining = STAGE_ORDER[1:]
        assert _next_stage("requirements", remaining) is None

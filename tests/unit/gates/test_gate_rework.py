"""Tests for gate rework decisions — each gate sets rework_decision on failure (Phase 1)."""

from __future__ import annotations

from typing import Any

import pytest

from colette.config import Settings
from colette.gates.design_gate import DesignGate
from colette.gates.implementation_gate import ImplementationGate
from colette.gates.requirements_gate import RequirementsGate
from colette.gates.staging_gate import StagingGate
from colette.gates.testing_gate import TestingGate


def _make_state(stage: str, handoff: dict[str, Any]) -> dict[str, Any]:
    return {"handoffs": {stage: handoff}}


class TestRequirementsGateRework:
    @pytest.mark.asyncio
    async def test_pass_has_no_rework(self) -> None:
        state = _make_state(
            "requirements",
            {
                "completeness_score": 0.90,
                "functional_requirements": [
                    {"acceptance_criteria": ["AC1"]},
                ],
            },
        )
        result = await RequirementsGate().evaluate(state)
        assert result.passed is True
        assert result.rework_decision == "pass"
        assert result.rework_target_stage is None

    @pytest.mark.asyncio
    async def test_failure_sets_rework_self(self) -> None:
        state = _make_state(
            "requirements",
            {"completeness_score": 0.50, "functional_requirements": []},
        )
        result = await RequirementsGate().evaluate(state)
        assert result.passed is False
        assert result.rework_decision == "rework_self"
        assert result.rework_target_stage == "requirements"


class TestDesignGateRework:
    @pytest.mark.asyncio
    async def test_pass_has_no_rework(self) -> None:
        state = _make_state(
            "design",
            {
                "openapi_spec": "openapi: 3.0.0\ninfo: ...",
                "architecture_summary": "Summary",
                "tech_stack": {"backend": "python"},
                "db_entities": [{"name": "users"}],
            },
        )
        result = await DesignGate().evaluate(state)
        assert result.passed is True
        assert result.rework_decision == "pass"

    @pytest.mark.asyncio
    async def test_failure_rework_self(self) -> None:
        state = _make_state(
            "design",
            {
                "openapi_spec": "",
                "architecture_summary": "Summary",
                "tech_stack": {"backend": "python"},
                "db_entities": [{"name": "users"}],
            },
        )
        result = await DesignGate().evaluate(state)
        assert result.passed is False
        assert result.rework_decision == "rework_self"
        assert result.rework_target_stage == "design"

    @pytest.mark.asyncio
    async def test_failure_upstream_rework(self) -> None:
        """Design gate failure: 'Architecture summary missing' contains upstream keyword."""
        state = _make_state("design", {})
        gate = DesignGate()
        result = await gate.evaluate(state)
        assert result.passed is False
        # "Architecture summary missing" contains "architecture" keyword -> upstream.
        assert result.rework_decision == "rework_target"
        assert result.rework_target_stage == "requirements"


class TestImplementationGateRework:
    @pytest.mark.asyncio
    async def test_pass_has_no_rework(self) -> None:
        state = _make_state(
            "implementation",
            {
                "files_changed": [{"path": "app.py"}],
                "lint_passed": True,
                "type_check_passed": True,
                "build_passed": True,
                "git_ref": "abc123",
            },
        )
        result = await ImplementationGate().evaluate(state)
        assert result.passed is True
        assert result.rework_decision == "pass"

    @pytest.mark.asyncio
    async def test_failure_rework_self(self) -> None:
        state = _make_state("implementation", {"files_changed": []})
        result = await ImplementationGate().evaluate(state)
        assert result.passed is False
        assert result.rework_decision == "rework_self"
        assert result.rework_target_stage == "implementation"


class TestTestingGateRework:
    @pytest.mark.asyncio
    async def test_pass_has_no_rework(self) -> None:
        state = _make_state(
            "testing",
            {
                "overall_line_coverage": 85.0,
                "overall_branch_coverage": 75.0,
                "security_findings": [],
                "contract_tests_passed": True,
                "deploy_readiness_score": 80,
            },
        )
        settings = Settings()
        result = await TestingGate(settings=settings).evaluate(state)
        assert result.passed is True
        assert result.rework_decision == "pass"

    @pytest.mark.asyncio
    async def test_failure_with_contract_routes_to_design(self) -> None:
        """Contract test failure contains 'contract' keyword -> upstream -> design."""
        state = _make_state(
            "testing",
            {
                "overall_line_coverage": 50.0,
                "overall_branch_coverage": 40.0,
                "security_findings": [],
                "contract_tests_passed": False,
                "deploy_readiness_score": 50,
            },
        )
        settings = Settings()
        result = await TestingGate(settings=settings).evaluate(state)
        assert result.passed is False
        # "Contract tests did not pass" contains "contract" -> upstream -> design.
        assert result.rework_target_stage == "design"

    @pytest.mark.asyncio
    async def test_failure_coverage_only_routes_to_implementation(self) -> None:
        """Pure coverage failure (no upstream keywords) routes to implementation."""
        state = _make_state(
            "testing",
            {
                "overall_line_coverage": 50.0,
                "overall_branch_coverage": 40.0,
                "security_findings": [],
                "contract_tests_passed": True,
                "deploy_readiness_score": 80,
            },
        )
        settings = Settings()
        result = await TestingGate(settings=settings).evaluate(state)
        assert result.passed is False
        assert result.rework_target_stage == "implementation"


class TestStagingGateRework:
    @pytest.mark.asyncio
    async def test_pass_has_no_rework(self) -> None:
        state = _make_state(
            "deployment",
            {
                "targets": [{"health_check_url": "http://localhost/health"}],
                "rollback_command": "kubectl rollback",
                "slo_targets": {"latency_p99_ms": 200},
            },
        )
        result = await StagingGate().evaluate(state)
        assert result.passed is True
        assert result.rework_decision == "pass"

    @pytest.mark.asyncio
    async def test_failure_rework_to_testing(self) -> None:
        state = _make_state("deployment", {})
        result = await StagingGate().evaluate(state)
        assert result.passed is False
        assert result.rework_target_stage == "testing"

"""Tests for all 6 quality gate implementations."""

from __future__ import annotations

import pytest

from colette.gates import (
    DesignGate,
    ImplementationGate,
    ProductionGate,
    RequirementsGate,
    StagingGate,
    TestingGate,
    create_default_registry,
)
from colette.orchestrator.state import create_initial_state


def _state_with_handoff(stage: str, handoff: dict) -> dict:
    state = dict(create_initial_state("test"))
    state["handoffs"] = {stage: handoff}
    return state


class TestRequirementsGate:
    @pytest.mark.asyncio
    async def test_passes_with_valid_handoff(self) -> None:
        state = _state_with_handoff(
            "requirements",
            {
                "completeness_score": 0.90,
                "functional_requirements": [
                    {"id": "US-REQ-001", "acceptance_criteria": ["done"]},
                ],
            },
        )
        result = await RequirementsGate().evaluate(state)
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_fails_low_completeness(self) -> None:
        state = _state_with_handoff(
            "requirements",
            {
                "completeness_score": 0.50,
                "functional_requirements": [
                    {"id": "US-REQ-001", "acceptance_criteria": ["done"]},
                ],
            },
        )
        result = await RequirementsGate().evaluate(state)
        assert result.passed is False
        assert any("0.50" in r for r in result.failure_reasons)

    @pytest.mark.asyncio
    async def test_fails_no_requirements(self) -> None:
        state = _state_with_handoff(
            "requirements",
            {
                "completeness_score": 0.90,
                "functional_requirements": [],
            },
        )
        result = await RequirementsGate().evaluate(state)
        assert result.passed is False


class TestDesignGate:
    @pytest.mark.asyncio
    async def test_passes_with_valid_handoff(self) -> None:
        state = _state_with_handoff(
            "design",
            {
                "openapi_spec": '{"openapi":"3.1.0","info":{"title":"API"}}',
                "architecture_summary": "Microservices",
                "tech_stack": {"backend": "Python"},
                "db_entities": [{"name": "users"}],
            },
        )
        result = await DesignGate().evaluate(state)
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_fails_missing_openapi(self) -> None:
        state = _state_with_handoff(
            "design",
            {
                "openapi_spec": "",
                "architecture_summary": "Arch",
                "tech_stack": {"backend": "Python"},
                "db_entities": [{"name": "users"}],
            },
        )
        result = await DesignGate().evaluate(state)
        assert result.passed is False


class TestImplementationGate:
    @pytest.mark.asyncio
    async def test_passes_all_checks(self) -> None:
        state = _state_with_handoff(
            "implementation",
            {
                "lint_passed": True,
                "type_check_passed": True,
                "build_passed": True,
                "files_changed": [{"path": "app.py"}],
                "git_ref": "main",
            },
        )
        result = await ImplementationGate().evaluate(state)
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_lint_advisory_still_passes(self) -> None:
        """LLM-based verification flags are advisory — gate passes if files exist."""
        state = _state_with_handoff(
            "implementation",
            {
                "lint_passed": False,
                "type_check_passed": True,
                "build_passed": True,
                "files_changed": [{"path": "app.py"}],
                "git_ref": "main",
            },
        )
        result = await ImplementationGate().evaluate(state)
        assert result.passed is True
        assert result.score < 1.0  # advisory flags lower the score
        assert any("advisory" in r for r in result.failure_reasons)

    @pytest.mark.asyncio
    async def test_fails_no_files(self) -> None:
        """Gate fails when no files were generated."""
        state = _state_with_handoff(
            "implementation",
            {
                "lint_passed": True,
                "type_check_passed": True,
                "build_passed": True,
                "files_changed": [],
                "git_ref": "main",
            },
        )
        result = await ImplementationGate().evaluate(state)
        assert result.passed is False


class TestTestingGate:
    @pytest.mark.asyncio
    async def test_passes_with_good_coverage(self) -> None:
        state = _state_with_handoff(
            "testing",
            {
                "overall_line_coverage": 85.0,
                "overall_branch_coverage": 75.0,
                "security_findings": [],
                "contract_tests_passed": True,
                "deploy_readiness_score": 90,
            },
        )
        result = await TestingGate().evaluate(state)
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_fails_low_coverage(self) -> None:
        state = _state_with_handoff(
            "testing",
            {
                "overall_line_coverage": 50.0,
                "overall_branch_coverage": 40.0,
                "security_findings": [],
                "contract_tests_passed": True,
                "deploy_readiness_score": 90,
            },
        )
        result = await TestingGate().evaluate(state)
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_fails_blocking_security_findings(self) -> None:
        state = _state_with_handoff(
            "testing",
            {
                "overall_line_coverage": 85.0,
                "overall_branch_coverage": 75.0,
                "security_findings": [{"severity": "CRITICAL", "id": "CVE-1"}],
                "contract_tests_passed": True,
                "deploy_readiness_score": 90,
            },
        )
        result = await TestingGate().evaluate(state)
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_configurable_thresholds_relax_gate(self) -> None:
        """A settings object with relaxed thresholds should let borderline data pass."""
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.gate_min_line_coverage = 50.0
        settings.gate_min_branch_coverage = 40.0
        settings.gate_max_blocking_security_findings = 2
        settings.gate_min_deploy_readiness = 60

        state = _state_with_handoff(
            "testing",
            {
                "overall_line_coverage": 55.0,
                "overall_branch_coverage": 45.0,
                "security_findings": [{"severity": "HIGH", "id": "H1"}],
                "contract_tests_passed": True,
                "deploy_readiness_score": 65,
            },
        )
        result = await TestingGate(settings=settings).evaluate(state)
        assert result.passed is True


class TestStagingGate:
    @pytest.mark.asyncio
    async def test_passes_with_health_checks(self) -> None:
        state = _state_with_handoff(
            "deployment",
            {
                "targets": [{"environment": "staging", "health_check_url": "http://h"}],
                "rollback_command": "rollback",
                "slo_targets": {"availability": "99.9%"},
            },
        )
        result = await StagingGate().evaluate(state)
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_fails_no_targets(self) -> None:
        state = _state_with_handoff(
            "deployment",
            {
                "targets": [],
                "rollback_command": "rollback",
                "slo_targets": {"availability": "99.9%"},
            },
        )
        result = await StagingGate().evaluate(state)
        assert result.passed is False


class TestProductionGate:
    @pytest.mark.asyncio
    async def test_passes_with_staging_and_approval(self) -> None:
        state = dict(create_initial_state("test"))
        state["quality_gate_results"] = {"staging": {"passed": True}}
        state["approval_decisions"] = [{"stage": "production", "status": "approved"}]
        result = await ProductionGate().evaluate(state)
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_fails_without_staging(self) -> None:
        state = dict(create_initial_state("test"))
        state["approval_decisions"] = [{"stage": "production", "status": "approved"}]
        result = await ProductionGate().evaluate(state)
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_fails_without_approval(self) -> None:
        state = dict(create_initial_state("test"))
        state["quality_gate_results"] = {"staging": {"passed": True}}
        result = await ProductionGate().evaluate(state)
        assert result.passed is False


class TestDefaultRegistry:
    def test_has_six_gates(self) -> None:
        registry = create_default_registry()
        assert len(registry.all_gates()) == 6

    def test_all_gate_names(self) -> None:
        registry = create_default_registry()
        names = set(registry.all_gates().keys())
        assert names == {
            "requirements",
            "design",
            "implementation",
            "testing",
            "staging",
            "production",
        }

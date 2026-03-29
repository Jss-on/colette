"""Tests for handoff schemas (FR-ORC-020/021/022/024)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from colette.schemas.base import DEFAULT_MAX_HANDOFF_CHARS, HandoffSchema
from colette.schemas.common import (
    ApprovalRecord,
    ApprovalStatus,
    ApprovalTier,
    Priority,
    QualityGateResult,
    SecurityFinding,
    Severity,
    SuiteResult,
    UserStory,
)
from colette.schemas.deployment import DeploymentToMonitoringHandoff
from colette.schemas.design import DesignToImplementationHandoff, ImplementationTask
from colette.schemas.implementation import ImplementationToTestingHandoff
from colette.schemas.requirements import RequirementsToDesignHandoff
from colette.schemas.testing import TestingToDeploymentHandoff

# ── Base HandoffSchema ───────────────────────────────────────────────


class TestHandoffSchemaBase:
    def test_defaults(self) -> None:
        h = HandoffSchema(
            schema_version="1.0.0",
            project_id="proj-001",
            source_stage="requirements",
            target_stage="design",
        )
        assert h.schema_version == "1.0.0"
        assert h.quality_gate_passed is False
        assert h.metadata == {}
        assert h.created_at is not None

    def test_version_compatible(self) -> None:
        h = HandoffSchema(
            schema_version="1.2.0",
            project_id="p",
            source_stage="a",
            target_stage="b",
        )
        h.check_version_compatible("1.0.0")  # same major — should not raise

    def test_version_mismatch_raises(self) -> None:
        h = HandoffSchema(
            schema_version="2.0.0",
            project_id="p",
            source_stage="a",
            target_stage="b",
        )
        with pytest.raises(ValueError, match="version mismatch"):
            h.check_version_compatible("1.0.0")

    def test_size_limit_enforcement(self) -> None:
        """FR-ORC-024: handoff exceeding size limit raises ValueError."""
        with pytest.raises(ValidationError, match="size limit"):
            HandoffSchema(
                schema_version="1.0.0",
                project_id="p",
                source_stage="a",
                target_stage="b",
                metadata={"bloat": "x" * (DEFAULT_MAX_HANDOFF_CHARS + 1000)},
            )

    def test_estimated_tokens(self) -> None:
        h = HandoffSchema(
            schema_version="1.0.0",
            project_id="p",
            source_stage="a",
            target_stage="b",
        )
        tokens = h.estimated_tokens()
        assert tokens > 0

    def test_json_roundtrip(self) -> None:
        h = HandoffSchema(
            schema_version="1.0.0",
            project_id="proj-002",
            source_stage="design",
            target_stage="implementation",
            quality_gate_passed=True,
        )
        json_str = h.to_json()
        restored = HandoffSchema.from_json(json_str)
        assert restored.project_id == "proj-002"
        assert restored.quality_gate_passed is True

    def test_to_dict(self) -> None:
        h = HandoffSchema(
            schema_version="1.0.0",
            project_id="p",
            source_stage="a",
            target_stage="b",
        )
        d = h.to_dict()
        assert isinstance(d, dict)
        assert d["project_id"] == "p"


# ── Common sub-models ────────────────────────────────────────────────


class TestCommonModels:
    def test_user_story_requires_acceptance_criteria(self) -> None:
        with pytest.raises(ValidationError):
            UserStory(
                id="US-REQ-001",
                title="t",
                persona="user",
                goal="g",
                benefit="b",
                acceptance_criteria=[],  # min_length=1
            )

    def test_user_story_valid(self) -> None:
        us = UserStory(
            id="US-REQ-001",
            title="Login",
            persona="user",
            goal="log in",
            benefit="access features",
            acceptance_criteria=["Can submit form"],
            priority=Priority.MUST,
        )
        assert us.id == "US-REQ-001"

    def test_quality_gate_result(self) -> None:
        qg = QualityGateResult(
            gate_name="req_to_design",
            passed=True,
            score=0.90,
            criteria_results={"completeness": True, "stories_valid": True},
        )
        assert qg.passed
        assert qg.score == 0.90

    def test_quality_gate_score_bounds(self) -> None:
        with pytest.raises(ValidationError):
            QualityGateResult(gate_name="g", passed=False, score=1.5)

    def test_approval_record(self) -> None:
        ar = ApprovalRecord(
            reviewer_id="rev-1",
            status=ApprovalStatus.APPROVED,
            tier=ApprovalTier.T0_CRITICAL,
        )
        assert ar.status == "approved"

    def test_security_finding(self) -> None:
        sf = SecurityFinding(
            id="SF-001",
            severity=Severity.HIGH,
            category="sql_injection",
            description="Unparameterized query",
        )
        assert sf.severity == "HIGH"

    def test_suite_result_coverage_bounds(self) -> None:
        with pytest.raises(ValidationError):
            SuiteResult(category="unit", line_coverage=101.0)


# ── Requirements → Design ────────────────────────────────────────────


class TestRequirementsHandoff:
    def _make_valid(self, **overrides: object) -> RequirementsToDesignHandoff:
        defaults: dict[str, object] = {
            "project_id": "p1",
            "project_overview": "A CRUD app",
            "functional_requirements": [
                UserStory(
                    id="US-REQ-001",
                    title="Login",
                    persona="user",
                    goal="log in",
                    benefit="access",
                    acceptance_criteria=["works"],
                )
            ],
            "completeness_score": 0.90,
        }
        defaults.update(overrides)
        return RequirementsToDesignHandoff(**defaults)  # type: ignore[arg-type]

    def test_valid_construction(self) -> None:
        h = self._make_valid()
        assert h.source_stage == "requirements"
        assert h.target_stage == "design"
        assert h.completeness_score == 0.90

    def test_requires_functional_requirements(self) -> None:
        with pytest.raises(ValidationError):
            self._make_valid(functional_requirements=[])

    def test_completeness_score_bounds(self) -> None:
        with pytest.raises(ValidationError):
            self._make_valid(completeness_score=1.5)


# ── Design → Implementation ──────────────────────────────────────────


class TestDesignHandoff:
    def test_valid_construction(self) -> None:
        h = DesignToImplementationHandoff(
            project_id="p1",
            architecture_summary="Monolith with REST API",
            tech_stack={"frontend": "Next.js", "backend": "FastAPI"},
            openapi_spec='{"openapi":"3.1.0"}',
        )
        assert h.source_stage == "design"
        assert h.tech_stack["frontend"] == "Next.js"

    def test_implementation_task(self) -> None:
        t = ImplementationTask(id="T-001", description="Build login page")
        assert t.complexity == "M"


# ── Implementation → Testing ─────────────────────────────────────────


class TestImplementationHandoff:
    def test_valid_construction(self) -> None:
        h = ImplementationToTestingHandoff(
            project_id="p1",
            git_repo_url="https://github.com/test/repo",
            git_ref="feature/auth",
            lint_passed=True,
            type_check_passed=True,
            build_passed=True,
        )
        assert h.lint_passed
        assert h.source_stage == "implementation"


# ── Testing → Deployment ─────────────────────────────────────────────


class TestTestingHandoff:
    def test_valid_construction(self) -> None:
        h = TestingToDeploymentHandoff(
            project_id="p1",
            overall_line_coverage=85.0,
            overall_branch_coverage=72.0,
            deploy_readiness_score=80,
            contract_tests_passed=True,
        )
        assert h.deploy_readiness_score == 80

    def test_readiness_score_bounds(self) -> None:
        with pytest.raises(ValidationError):
            TestingToDeploymentHandoff(
                project_id="p1",
                deploy_readiness_score=150,
            )


# ── Deployment → Monitoring ──────────────────────────────────────────


class TestDeploymentHandoff:
    def test_valid_construction(self) -> None:
        h = DeploymentToMonitoringHandoff(
            project_id="p1",
            deployment_id="dep-001",
            docker_images=["app:v1.0"],
            slo_targets={"availability": "99.9%"},
        )
        assert h.deployment_id == "dep-001"
        assert h.source_stage == "deployment"

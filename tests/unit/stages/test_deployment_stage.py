"""Tests for the Deployment stage (Phase 6)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from colette.schemas.common import (
    GeneratedFile,
    SecurityFinding,
    Severity,
    StageName,
    SuiteResult,
)
from colette.schemas.testing import TestingToDeploymentHandoff
from colette.stages.deployment.cicd_engineer import CICDResult
from colette.stages.deployment.infra_engineer import InfraResult
from colette.stages.deployment.stage import run_stage
from colette.stages.deployment.supervisor import (
    _build_deployment_targets,
    _evaluate_quality,
    _testing_to_context,
    assemble_handoff,
    supervise_deployment,
)

# ── Fixtures ────────────────────────────────────────────────────────────


def _make_testing_handoff() -> TestingToDeploymentHandoff:
    return TestingToDeploymentHandoff(
        project_id="proj-1",
        test_results=[
            SuiteResult(category="unit", total=25, passed=25, line_coverage=85.0),
            SuiteResult(category="integration", total=12, passed=12),
        ],
        overall_line_coverage=89.5,
        overall_branch_coverage=75.0,
        security_findings=[
            SecurityFinding(
                id="SEC-001",
                severity=Severity.MEDIUM,
                category="hardcoded-config",
                description="Default port hardcoded.",
            ),
        ],
        contract_tests_passed=True,
        deploy_readiness_score=92,
        git_ref="main",
        quality_gate_passed=True,
    )


def _make_cicd_result() -> CICDResult:
    return CICDResult(
        pipeline_files=[
            GeneratedFile(
                path=".github/workflows/ci.yml",
                content="name: CI\non: push\njobs: ...",
                language="yaml",
            ),
            GeneratedFile(
                path=".github/workflows/deploy.yml",
                content="name: Deploy\non: workflow_dispatch\njobs: ...",
                language="yaml",
            ),
        ],
        platform="github_actions",
        stages=["lint", "test", "build", "deploy-staging", "deploy-production"],
        has_rollback=True,
        rollback_command="kubectl rollout undo deployment/app",
        staging_auto_deploy=True,
        production_gate=True,
        notes="Uses GitHub Environments for approval.",
    )


def _make_infra_result() -> InfraResult:
    return InfraResult(
        files=[
            GeneratedFile(
                path="Dockerfile",
                content="FROM python:3.13-slim AS builder\n...",
                language="dockerfile",
            ),
            GeneratedFile(
                path="docker-compose.yml",
                content="version: '3.8'\nservices: ...",
                language="yaml",
            ),
            GeneratedFile(
                path="k8s/deployment.yaml",
                content="apiVersion: apps/v1\nkind: Deployment\n...",
                language="yaml",
            ),
        ],
        docker_images=["app-backend:latest", "app-frontend:latest"],
        has_kubernetes=True,
        deployment_strategy="rolling",
        secrets_strategy="sealed-secrets",
        tls_configured=True,
        health_check_paths=["/health", "/readyz"],
        notes="Multi-stage Docker build with non-root user.",
    )


# ── _testing_to_context ───────────────────────────────────────────────


class TestTestingToContext:
    def test_includes_coverage(self) -> None:
        ctx = _testing_to_context(_make_testing_handoff())
        assert "89.5%" in ctx

    def test_includes_security_summary(self) -> None:
        ctx = _testing_to_context(_make_testing_handoff())
        assert "hardcoded-config" in ctx

    def test_includes_git_ref(self) -> None:
        ctx = _testing_to_context(_make_testing_handoff())
        assert "main" in ctx

    def test_includes_readiness_score(self) -> None:
        ctx = _testing_to_context(_make_testing_handoff())
        assert "92" in ctx


# ── _build_deployment_targets ─────────────────────────────────────────


class TestBuildDeploymentTargets:
    def test_creates_staging_target(self) -> None:
        targets = _build_deployment_targets(_make_infra_result())
        staging = [t for t in targets if t.environment == "staging"]
        assert len(staging) == 1
        assert staging[0].health_check_url is not None
        assert "/health" in staging[0].health_check_url  # type: ignore[operator]

    def test_creates_production_when_k8s(self) -> None:
        targets = _build_deployment_targets(_make_infra_result())
        prod = [t for t in targets if t.environment == "production"]
        assert len(prod) == 1
        assert prod[0].replicas == 3

    def test_no_production_without_k8s(self) -> None:
        infra = InfraResult(
            docker_images=["app:latest"],
            has_kubernetes=False,
            health_check_paths=["/health"],
        )
        targets = _build_deployment_targets(infra)
        prod = [t for t in targets if t.environment == "production"]
        assert len(prod) == 0

    def test_handles_no_health_checks(self) -> None:
        infra = InfraResult(docker_images=["app:latest"], health_check_paths=[])
        targets = _build_deployment_targets(infra)
        assert targets[0].health_check_url is None


# ── _evaluate_quality ─────────────────────────────────────────────────


class TestEvaluateQuality:
    def test_passes_with_complete_results(self) -> None:
        assert _evaluate_quality(_make_cicd_result(), _make_infra_result()) is True

    def test_fails_no_pipeline_files(self) -> None:
        cicd = CICDResult(
            pipeline_files=[],
            has_rollback=True,
            staging_auto_deploy=True,
            production_gate=True,
        )
        assert _evaluate_quality(cicd, _make_infra_result()) is False

    def test_fails_no_docker_images(self) -> None:
        infra = InfraResult(docker_images=[])
        assert _evaluate_quality(_make_cicd_result(), infra) is False

    def test_fails_no_rollback(self) -> None:
        cicd = CICDResult(
            pipeline_files=[
                GeneratedFile(path="ci.yml", content="...", language="yaml"),
            ],
            has_rollback=False,
            staging_auto_deploy=True,
            production_gate=True,
        )
        assert _evaluate_quality(cicd, _make_infra_result()) is False

    def test_fails_no_staging_auto_deploy(self) -> None:
        cicd = CICDResult(
            pipeline_files=[
                GeneratedFile(path="ci.yml", content="...", language="yaml"),
            ],
            has_rollback=True,
            staging_auto_deploy=False,
            production_gate=True,
        )
        assert _evaluate_quality(cicd, _make_infra_result()) is False

    def test_fails_no_production_gate(self) -> None:
        cicd = CICDResult(
            pipeline_files=[
                GeneratedFile(path="ci.yml", content="...", language="yaml"),
            ],
            has_rollback=True,
            staging_auto_deploy=True,
            production_gate=False,
        )
        assert _evaluate_quality(cicd, _make_infra_result()) is False


# ── assemble_handoff ──────────────────────────────────────────────────


class TestAssembleHandoff:
    def test_basic_assembly(self) -> None:
        handoff = assemble_handoff(
            "proj-1", _make_testing_handoff(), _make_cicd_result(), _make_infra_result()
        )
        assert handoff.project_id == "proj-1"
        assert handoff.source_stage == "deployment"
        assert handoff.target_stage == "monitoring"
        assert handoff.quality_gate_passed is True

    def test_deployment_id_format(self) -> None:
        handoff = assemble_handoff(
            "proj-1", _make_testing_handoff(), _make_cicd_result(), _make_infra_result()
        )
        assert handoff.deployment_id.startswith("deploy-proj-1-")

    def test_slo_targets_populated(self) -> None:
        handoff = assemble_handoff(
            "proj-1", _make_testing_handoff(), _make_cicd_result(), _make_infra_result()
        )
        assert "availability" in handoff.slo_targets
        assert "p99_latency" in handoff.slo_targets

    def test_rollback_command_from_cicd(self) -> None:
        handoff = assemble_handoff(
            "proj-1", _make_testing_handoff(), _make_cicd_result(), _make_infra_result()
        )
        assert handoff.rollback_command == "kubectl rollout undo deployment/app"

    def test_docker_images_from_infra(self) -> None:
        handoff = assemble_handoff(
            "proj-1", _make_testing_handoff(), _make_cicd_result(), _make_infra_result()
        )
        assert "app-backend:latest" in handoff.docker_images
        assert "app-frontend:latest" in handoff.docker_images

    def test_git_ref_from_testing(self) -> None:
        handoff = assemble_handoff(
            "proj-1", _make_testing_handoff(), _make_cicd_result(), _make_infra_result()
        )
        assert handoff.git_ref == "main"


# ── supervise_deployment ──────────────────────────────────────────────


class TestSuperviseDeployment:
    @pytest.mark.asyncio
    async def test_produces_handoff(self, settings: object) -> None:
        testing = _make_testing_handoff()

        with (
            patch(
                "colette.stages.deployment.supervisor.run_cicd_engineer",
                new_callable=AsyncMock,
                return_value=_make_cicd_result(),
            ),
            patch(
                "colette.stages.deployment.supervisor.run_infra_engineer",
                new_callable=AsyncMock,
                return_value=_make_infra_result(),
            ),
        ):
            handoff = await supervise_deployment(
                "proj-1",
                testing,
                settings=settings,  # type: ignore[arg-type]
            )

        assert handoff.project_id == "proj-1"
        assert handoff.quality_gate_passed is True
        assert len(handoff.targets) >= 1

    @pytest.mark.asyncio
    async def test_both_agents_required(self, settings: object) -> None:
        testing = _make_testing_handoff()

        with (
            patch(
                "colette.stages.deployment.supervisor.run_cicd_engineer",
                new_callable=AsyncMock,
                side_effect=RuntimeError("CI/CD agent failed"),
            ),
            patch(
                "colette.stages.deployment.supervisor.run_infra_engineer",
                new_callable=AsyncMock,
                return_value=_make_infra_result(),
            ),
            pytest.raises(RuntimeError, match="CI/CD agent failed"),
        ):
            await supervise_deployment(
                "proj-1",
                testing,
                settings=settings,  # type: ignore[arg-type]
            )


# ── run_stage ─────────────────────────────────────────────────────────


class TestRunStage:
    @pytest.mark.asyncio
    async def test_raises_on_missing_testing_handoff(self) -> None:
        state = {
            "project_id": "test-proj",
            "stage_statuses": {},
            "handoffs": {},
        }
        with pytest.raises(ValueError, match="requires a completed Testing handoff"):
            await run_stage(state)

    @pytest.mark.asyncio
    async def test_produces_valid_state_update(self) -> None:
        testing = _make_testing_handoff()
        state = {
            "project_id": "test-proj",
            "stage_statuses": {},
            "handoffs": {
                StageName.TESTING.value: testing.to_dict(),
            },
        }

        with (
            patch(
                "colette.stages.deployment.supervisor.run_cicd_engineer",
                new_callable=AsyncMock,
                return_value=_make_cicd_result(),
            ),
            patch(
                "colette.stages.deployment.supervisor.run_infra_engineer",
                new_callable=AsyncMock,
                return_value=_make_infra_result(),
            ),
            patch("colette.stages.deployment.stage.Settings"),
        ):
            result = await run_stage(state)

        assert result["current_stage"] == "deployment"
        assert result["stage_statuses"]["deployment"] == "completed"
        assert "deployment" in result["handoffs"]
        handoff = result["handoffs"]["deployment"]
        assert handoff["source_stage"] == "deployment"
        assert len(result["progress_events"]) == 1

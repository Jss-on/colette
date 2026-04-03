"""Deployment Supervisor — orchestrates CI/CD engineer and infra engineer (FR-DEP-*)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from colette.schemas.common import DeploymentTarget
from colette.schemas.deployment import DeploymentToMonitoringHandoff
from colette.schemas.testing import TestingToDeploymentHandoff
from colette.stages.deployment.cicd_engineer import CICDResult, run_cicd_engineer
from colette.stages.deployment.infra_engineer import InfraResult, run_infra_engineer

if TYPE_CHECKING:
    from colette.config import Settings

logger = structlog.get_logger(__name__)


# ── Testing-to-context conversion ────────────────────────────────────


def _testing_to_context(handoff: TestingToDeploymentHandoff) -> str:
    """Convert the Testing handoff into human-readable context for deploy agents."""
    sections: list[str] = ["# Test Results Summary"]

    sections.append("\n## Coverage")
    sections.append(f"- Line coverage: {handoff.overall_line_coverage:.1f}%")
    sections.append(f"- Branch coverage: {handoff.overall_branch_coverage:.1f}%")

    if handoff.test_results:
        sections.append("\n## Test Suites")
        for suite in handoff.test_results:
            sections.append(f"- {suite.category}: {suite.passed}/{suite.total} passed")

    contract_status = "PASSED" if handoff.contract_tests_passed else "FAILED"
    sections.append(f"\n## Contract Tests: {contract_status}")
    if handoff.contract_deviations:
        sections.append("### Deviations")
        for dev in handoff.contract_deviations:
            sections.append(f"- {dev}")

    if handoff.security_findings:
        sections.append(f"\n## Security Findings ({len(handoff.security_findings)})")
        for finding in handoff.security_findings[:10]:
            sections.append(f"- [{finding.severity}] {finding.category}: {finding.description}")

    sections.append(f"\n## Deploy Readiness Score: {handoff.deploy_readiness_score}/100")

    if handoff.blocking_issues:
        sections.append("\n## Blocking Issues")
        for issue in handoff.blocking_issues:
            sections.append(f"- {issue}")

    sections.append(f"\n## Git Ref: {handoff.git_ref}")

    return "\n".join(sections)


# ── Deployment target construction ────────────────────────────────────


def _build_deployment_targets(infra: InfraResult) -> list[DeploymentTarget]:
    """Create DeploymentTarget entries from infra output."""
    targets: list[DeploymentTarget] = []

    health_url = None
    if infra.health_check_paths:
        health_url = f"https://staging.example.com{infra.health_check_paths[0]}"

    targets.append(
        DeploymentTarget(
            environment="staging",
            url="https://staging.example.com",
            health_check_url=health_url,
        )
    )

    if infra.has_kubernetes:
        prod_health_url = None
        if infra.health_check_paths:
            prod_health_url = f"https://app.example.com{infra.health_check_paths[0]}"
        targets.append(
            DeploymentTarget(
                environment="production",
                url="https://app.example.com",
                health_check_url=prod_health_url,
                replicas=3,
            )
        )

    return targets


# ── Quality evaluation ────────────────────────────────────────────────


def _evaluate_quality(cicd: CICDResult, infra: InfraResult) -> bool:
    """Evaluate deployment quality gate.

    Passes when:
    - At least one pipeline file generated
    - At least one Docker image defined
    - Rollback is configured
    - Staging auto-deploy is present
    - Production gate is present
    """
    if not cicd.pipeline_files:
        return False
    if not infra.docker_images:
        return False
    if not cicd.has_rollback:
        return False
    if not cicd.staging_auto_deploy:
        return False
    return cicd.production_gate


# ── Handoff assembly ──────────────────────────────────────────────────


def assemble_handoff(
    project_id: str,
    testing_handoff: TestingToDeploymentHandoff,
    cicd: CICDResult,
    infra: InfraResult,
) -> DeploymentToMonitoringHandoff:
    """Assemble the Deployment-to-Monitoring handoff from agent outputs."""
    targets = _build_deployment_targets(infra)
    gate_passed = _evaluate_quality(cicd, infra)
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")

    slo_targets = {"availability": "99.9%", "p99_latency": "500ms"}

    return DeploymentToMonitoringHandoff(
        project_id=project_id,
        deployment_id=f"deploy-{project_id}-{timestamp}",
        targets=targets,
        docker_images=list(infra.docker_images),
        ci_pipeline_url="",
        git_ref=testing_handoff.git_ref,
        rollback_command=cicd.rollback_command,
        slo_targets=slo_targets,
        quality_gate_passed=gate_passed,
    )


# ── Main supervisor ───────────────────────────────────────────────────


async def supervise_deployment(
    project_id: str,
    testing_handoff: TestingToDeploymentHandoff,
    *,
    settings: Settings,
) -> DeploymentToMonitoringHandoff:
    """Orchestrate the Deployment stage (FR-DEP-*).

    Runs CI/CD engineer and infra engineer in parallel. Both are
    MUST requirements, so failure in either propagates.
    """
    logger.info("deployment_supervisor.start", project_id=project_id)

    deploy_context = _testing_to_context(testing_handoff)

    # Both agents are MUST — run in parallel, propagate failures
    cicd, infra = await asyncio.gather(
        run_cicd_engineer(deploy_context, settings=settings),
        run_infra_engineer(deploy_context, settings=settings),
    )

    handoff = assemble_handoff(project_id, testing_handoff, cicd, infra)

    all_deploy_files = [*cicd.pipeline_files, *infra.files]

    logger.info(
        "deployment_supervisor.complete",
        project_id=project_id,
        deployment_id=handoff.deployment_id,
        targets=len(handoff.targets),
        images=len(handoff.docker_images),
        gate_passed=handoff.quality_gate_passed,
    )
    return handoff, all_deploy_files

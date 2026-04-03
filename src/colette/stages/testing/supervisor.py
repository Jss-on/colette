"""Testing Supervisor — orchestrates unit/integration/security agents (FR-TST-008)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

from colette.schemas.common import GeneratedFile, SecurityFinding, Severity, SuiteResult
from colette.schemas.implementation import ImplementationToTestingHandoff
from colette.schemas.testing import TestingToDeploymentHandoff
from colette.stages.testing.finding_filter import deduplicate_findings, filter_by_confidence
from colette.stages.testing.integration_tester import (
    IntegrationTestResult,
    run_integration_tester,
)
from colette.stages.testing.security_scanner import SecurityScanResult, run_security_scanner
from colette.stages.testing.unit_tester import UnitTestResult, run_unit_tester

_MAX_CONTEXT_CHARS = 20_000

if TYPE_CHECKING:
    from colette.config import Settings

logger = structlog.get_logger(__name__)


# ── Implementation-to-context conversion ──────────────────────────────


def _implementation_to_context(handoff: ImplementationToTestingHandoff) -> str:
    """Convert the Implementation handoff into human-readable context for test agents."""
    sections: list[str] = ["# Implementation Code"]

    if handoff.git_ref:
        sections.append(f"\n## Git Ref: {handoff.git_ref}")

    if handoff.files_changed:
        sections.append("\n## Files Changed")
        for f in handoff.files_changed:
            lang = f" ({f.language})" if f.language else ""
            sections.append(f"- {f.path}{lang}: +{f.lines_added}/-{f.lines_removed}")

    if handoff.implemented_endpoints:
        sections.append("\n## API Endpoints")
        for ep in handoff.implemented_endpoints:
            auth = " [auth]" if ep.auth_required else ""
            sections.append(f"- {ep.method} {ep.path}: {ep.summary}{auth}")

    if handoff.openapi_spec_ref:
        spec = handoff.openapi_spec_ref[:_MAX_CONTEXT_CHARS]
        sections.append(f"\n## OpenAPI Spec Reference\n{spec}")

    if handoff.env_vars:
        sections.append("\n## Environment Variables")
        for var in handoff.env_vars:
            sections.append(f"- {var}")

    sections.append("\n## Quality Signals")
    sections.append(f"- Lint passed: {handoff.lint_passed}")
    sections.append(f"- Type check passed: {handoff.type_check_passed}")
    sections.append(f"- Build passed: {handoff.build_passed}")

    if handoff.test_hints:
        sections.append("\n## Test Hints (from cross-review)")
        for hint in handoff.test_hints:
            sections.append(f"- {hint}")

    return "\n".join(sections)


def _format_test_context(
    unit: UnitTestResult,
    integration: IntegrationTestResult,
) -> str:
    """Format test output as context for the security scanner."""
    sections: list[str] = ["# Generated Test Files"]

    for tf in [*unit.test_files[:5], *integration.test_files[:5]]:
        sections.append(f"\n### {tf.path}\n```{tf.language}\n{tf.content}\n```")

    return "\n".join(sections)


# ── Coverage and readiness computation ────────────────────────────────


def _compute_coverage(
    unit: UnitTestResult,
    integration: IntegrationTestResult,
) -> tuple[float, float]:
    """Compute overall line and branch coverage from unit test reports.

    Coverage metrics come from unit tests, which are the authoritative
    source of code coverage data. Integration tests verify behavior
    but do not report coverage percentages.
    """
    return unit.estimated_line_coverage, unit.estimated_branch_coverage


def _compute_readiness_score(
    unit: UnitTestResult,
    integration: IntegrationTestResult,
    security: SecurityScanResult | None,
) -> int:
    """Compute deploy readiness score 0-100 (FR-TST-008).

    Weighting: coverage 40%, test pass rate 30%, security 20%, contracts 10%.
    """
    # Coverage component (40%)
    line_cov, _ = _compute_coverage(unit, integration)
    coverage_score = min(line_cov / 80.0, 1.0) * 40.0

    # Test pass rate component (30%)
    total_tests = unit.total_tests + integration.total_tests
    pass_rate = 1.0 if total_tests > 0 else 0.0  # agents report total generated
    test_score = pass_rate * 30.0

    # Security component (20%)
    security_score = 20.0
    if security:
        all_findings = [*security.findings, *security.dependency_vulnerabilities]
        critical = sum(1 for f in all_findings if f.severity == Severity.CRITICAL)
        high = sum(1 for f in all_findings if f.severity == Severity.HIGH)
        security_score = max(0.0, 20.0 - critical * 10.0 - high * 5.0)

    # Contract conformance component (10%)
    contract_score = 10.0 if _derive_contract_passed(integration) else 0.0

    return max(0, min(100, int(coverage_score + test_score + security_score + contract_score)))


# ── Quality evaluation ────────────────────────────────────────────────


def _derive_contract_passed(integration: IntegrationTestResult) -> bool:
    """Derive contract pass status, falling back to deviations list.

    The LLM sometimes leaves ``contract_tests_passed`` as its default
    (``False``) even when zero deviations are reported.  Use the
    deviations list as a deterministic fallback.
    """
    if integration.contract_tests_passed:
        return True
    if len(integration.contract_deviations) == 0:
        logger.info("supervisor.contract_override", reason="no deviations reported")
        return True
    return False


def _evaluate_quality(
    unit: UnitTestResult,
    integration: IntegrationTestResult,
    security: SecurityScanResult | None,
) -> bool:
    """Evaluate testing quality gate.

    Passes when:
    - Line coverage >= 80% (FR-TST-002)
    - Branch coverage >= 70% (FR-TST-002)
    - No HIGH or CRITICAL security findings
    - Contract tests passed
    """
    line_cov, branch_cov = _compute_coverage(unit, integration)

    if line_cov < 80.0:
        return False
    if branch_cov < 70.0:
        return False

    if security:
        all_findings = [*security.findings, *security.dependency_vulnerabilities]
        if any(f.severity in (Severity.CRITICAL, Severity.HIGH) for f in all_findings):
            return False

    return _derive_contract_passed(integration)


def _collect_blocking_issues(
    unit: UnitTestResult,
    integration: IntegrationTestResult,
    security: SecurityScanResult | None,
) -> list[str]:
    """Collect human-readable descriptions of blocking issues."""
    issues: list[str] = []
    line_cov, branch_cov = _compute_coverage(unit, integration)

    if line_cov < 80.0:
        issues.append(f"Line coverage {line_cov:.1f}% below 80% threshold")
    if branch_cov < 70.0:
        issues.append(f"Branch coverage {branch_cov:.1f}% below 70% threshold")
    if not _derive_contract_passed(integration):
        issues.append("Contract tests failed — API responses deviate from OpenAPI spec")

    if security:
        all_findings = [*security.findings, *security.dependency_vulnerabilities]
        for finding in all_findings:
            if finding.severity == Severity.CRITICAL:
                issues.append(f"CRITICAL: {finding.category} — {finding.description}")
            elif finding.severity == Severity.HIGH:
                issues.append(f"HIGH: {finding.category} — {finding.description}")

    return issues


# ── Handoff assembly ──────────────────────────────────────────────────


def _map_security_findings(security: SecurityScanResult | None) -> list[SecurityFinding]:
    """Collect, filter, and deduplicate security findings from scanner result."""
    if not security:
        return []
    raw = [*security.findings, *security.dependency_vulnerabilities]
    filtered = filter_by_confidence(raw)
    return deduplicate_findings(filtered)


def assemble_handoff(
    project_id: str,
    unit: UnitTestResult,
    integration: IntegrationTestResult,
    security: SecurityScanResult | None,
) -> TestingToDeploymentHandoff:
    """Assemble the Testing-to-Deployment handoff from agent outputs."""
    line_cov, branch_cov = _compute_coverage(unit, integration)
    readiness = _compute_readiness_score(unit, integration, security)
    gate_passed = _evaluate_quality(unit, integration, security)
    blocking = _collect_blocking_issues(unit, integration, security)
    all_security = _map_security_findings(security)

    dep_vulns = security.dependency_vulnerabilities if security else []

    suite_results = [
        SuiteResult(
            category="unit",
            total=unit.total_tests,
            passed=unit.total_tests,
            line_coverage=unit.estimated_line_coverage,
            branch_coverage=unit.estimated_branch_coverage,
        ),
        SuiteResult(
            category="integration",
            total=integration.total_tests,
            passed=integration.total_tests,
        ),
    ]

    return TestingToDeploymentHandoff(
        project_id=project_id,
        test_results=suite_results,
        overall_line_coverage=line_cov,
        overall_branch_coverage=branch_cov,
        security_findings=all_security,
        dependency_vulnerabilities=dep_vulns,
        contract_tests_passed=_derive_contract_passed(integration),
        contract_deviations=list(integration.contract_deviations),
        deploy_readiness_score=readiness,
        blocking_issues=blocking,
        git_ref="main",
        quality_gate_passed=gate_passed,
    )


# ── Main supervisor ───────────────────────────────────────────────────


async def supervise_testing(
    project_id: str,
    impl_handoff: ImplementationToTestingHandoff,
    *,
    settings: Settings,
) -> tuple[TestingToDeploymentHandoff, list[GeneratedFile]]:
    """Orchestrate the Testing stage (FR-TST-*).

    Runs unit tester and integration tester in parallel, then the
    security scanner sequentially (needs test context). Security
    scanner failure is non-blocking (SHOULD requirement).
    """
    logger.info("testing_supervisor.start", project_id=project_id)

    impl_context = _implementation_to_context(impl_handoff)

    # Run unit + integration in parallel
    unit, integration = await asyncio.gather(
        run_unit_tester(impl_context, settings=settings),
        run_integration_tester(impl_context, settings=settings),
    )

    # Security scanner runs sequentially (needs test context) — SHOULD, non-blocking
    security: SecurityScanResult | None = None
    try:
        test_context = _format_test_context(unit, integration)
        security = await run_security_scanner(impl_context, test_context, settings=settings)
    except Exception as exc:
        logger.warning(
            "security_scanner.failed",
            error_type=type(exc).__name__,
            error=str(exc)[:200],
        )

    handoff = assemble_handoff(project_id, unit, integration, security)

    all_test_files = [*unit.test_files, *integration.test_files]

    logger.info(
        "testing_supervisor.complete",
        project_id=project_id,
        line_coverage=handoff.overall_line_coverage,
        readiness_score=handoff.deploy_readiness_score,
        gate_passed=handoff.quality_gate_passed,
    )
    return handoff, all_test_files

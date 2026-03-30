"""Tests for the Testing stage (Phase 6)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from colette.schemas.common import (
    EndpointSpec,
    FileDiff,
    GeneratedFile,
    SecurityFinding,
    Severity,
    StageName,
)
from colette.schemas.implementation import ImplementationToTestingHandoff
from colette.stages.testing.integration_tester import IntegrationTestResult
from colette.stages.testing.security_scanner import SecurityScanResult
from colette.stages.testing.stage import run_stage
from colette.stages.testing.supervisor import (
    _collect_blocking_issues,
    _compute_coverage,
    _compute_readiness_score,
    _evaluate_quality,
    _implementation_to_context,
    assemble_handoff,
    supervise_testing,
)
from colette.stages.testing.unit_tester import UnitTestResult

# ── Fixtures ────────────────────────────────────────────────────────────


def _make_impl_handoff() -> ImplementationToTestingHandoff:
    return ImplementationToTestingHandoff(
        project_id="proj-1",
        git_repo_url="https://github.com/example/app",
        git_ref="main",
        files_changed=[
            FileDiff(
                path="src/routes/todos.py",
                action="added",
                language="python",
                lines_added=50,
            ),
            FileDiff(
                path="src/components/TodoList.tsx",
                action="added",
                language="typescript",
                lines_added=30,
            ),
        ],
        implemented_endpoints=[
            EndpointSpec(method="GET", path="/api/v1/todos", summary="List todos"),
            EndpointSpec(method="POST", path="/api/v1/todos", summary="Create todo"),
        ],
        openapi_spec_ref='{"openapi":"3.1.0"}',
        env_vars=["DATABASE_URL", "JWT_SECRET"],
        lint_passed=True,
        type_check_passed=True,
        build_passed=True,
        test_hints=["[MEDIUM] type inconsistency: field name mismatch"],
        quality_gate_passed=True,
    )


def _make_unit_result() -> UnitTestResult:
    return UnitTestResult(
        test_files=[
            GeneratedFile(
                path="tests/test_todos.py",
                content="def test_list_todos(): assert True",
                language="python",
            ),
        ],
        framework="pytest",
        total_tests=25,
        estimated_line_coverage=85.0,
        estimated_branch_coverage=75.0,
        test_categories=["unit", "property-based"],
        notes="Covers all route handlers.",
    )


def _make_integration_result() -> IntegrationTestResult:
    return IntegrationTestResult(
        test_files=[
            GeneratedFile(
                path="tests/integration/test_api.py",
                content="def test_get_todos(): ...",
                language="python",
            ),
        ],
        framework="httpx",
        total_tests=12,
        endpoint_coverage=["GET /api/v1/todos", "POST /api/v1/todos"],
        contract_deviations=[],
        contract_tests_passed=True,
        e2e_flows_tested=["login", "create-todo"],
        notes="All endpoints tested.",
    )


def _make_security_result() -> SecurityScanResult:
    return SecurityScanResult(
        findings=[
            SecurityFinding(
                id="SEC-001",
                severity=Severity.MEDIUM,
                category="hardcoded-config",
                description="Default port hardcoded in config.",
                location="src/config.py",
                recommendation="Use environment variable.",
            ),
        ],
        dependency_vulnerabilities=[],
        accessibility_issues=["Missing alt text on logo image"],
        sast_tool="semgrep",
        has_blocking_findings=False,
        summary="No critical issues found.",
    )


def _make_security_result_blocking() -> SecurityScanResult:
    return SecurityScanResult(
        findings=[
            SecurityFinding(
                id="SEC-002",
                severity=Severity.CRITICAL,
                category="sql-injection",
                description="String concatenation in SQL query.",
                location="src/db/queries.py",
                recommendation="Use parameterized queries.",
            ),
        ],
        dependency_vulnerabilities=[
            SecurityFinding(
                id="CVE-2024-001",
                severity=Severity.CRITICAL,
                category="dependency-vuln",
                description="RCE in lodash < 4.17.21",
                recommendation="Upgrade lodash.",
            ),
        ],
        accessibility_issues=[],
        sast_tool="semgrep",
        has_blocking_findings=True,
        summary="Critical vulnerabilities found.",
    )


# ── _implementation_to_context ────────────────────────────────────────


class TestImplementationToContext:
    def test_includes_file_paths(self) -> None:
        ctx = _implementation_to_context(_make_impl_handoff())
        assert "src/routes/todos.py" in ctx

    def test_includes_endpoints(self) -> None:
        ctx = _implementation_to_context(_make_impl_handoff())
        assert "GET /api/v1/todos" in ctx
        assert "POST /api/v1/todos" in ctx

    def test_includes_test_hints(self) -> None:
        ctx = _implementation_to_context(_make_impl_handoff())
        assert "type inconsistency" in ctx

    def test_includes_env_vars(self) -> None:
        ctx = _implementation_to_context(_make_impl_handoff())
        assert "DATABASE_URL" in ctx

    def test_includes_quality_signals(self) -> None:
        ctx = _implementation_to_context(_make_impl_handoff())
        assert "Lint passed: True" in ctx


# ── _compute_coverage ─────────────────────────────────────────────────


class TestComputeCoverage:
    def test_returns_unit_coverage(self) -> None:
        unit = _make_unit_result()
        integration = _make_integration_result()
        line, branch = _compute_coverage(unit, integration)
        assert line == pytest.approx(85.0, abs=0.1)
        assert branch == pytest.approx(75.0, abs=0.1)

    def test_zero_integration_tests_same_result(self) -> None:
        unit = _make_unit_result()
        integration = IntegrationTestResult(total_tests=0)
        line, branch = _compute_coverage(unit, integration)
        assert line == pytest.approx(85.0, abs=0.1)
        assert branch == pytest.approx(75.0, abs=0.1)


# ── _compute_readiness_score ──────────────────────────────────────────


class TestComputeReadinessScore:
    def test_full_pass_high_score(self) -> None:
        score = _compute_readiness_score(
            _make_unit_result(), _make_integration_result(), _make_security_result()
        )
        assert score >= 80

    def test_low_coverage_reduces_score(self) -> None:
        unit = UnitTestResult(estimated_line_coverage=30.0, total_tests=5)
        integration = IntegrationTestResult(total_tests=3, contract_tests_passed=True)
        score = _compute_readiness_score(unit, integration, None)
        good_score = _compute_readiness_score(
            _make_unit_result(), _make_integration_result(), None
        )
        assert score < good_score

    def test_security_findings_reduce_score(self) -> None:
        score = _compute_readiness_score(
            _make_unit_result(), _make_integration_result(), _make_security_result_blocking()
        )
        good_score = _compute_readiness_score(
            _make_unit_result(), _make_integration_result(), _make_security_result()
        )
        assert score < good_score

    def test_floor_at_zero(self) -> None:
        unit = UnitTestResult(estimated_line_coverage=0.0, total_tests=0)
        integration = IntegrationTestResult(total_tests=0)
        score = _compute_readiness_score(unit, integration, _make_security_result_blocking())
        assert score >= 0


# ── _evaluate_quality ─────────────────────────────────────────────────


class TestEvaluateQuality:
    def test_passes_with_good_results(self) -> None:
        assert (
            _evaluate_quality(
                _make_unit_result(), _make_integration_result(), _make_security_result()
            )
            is True
        )

    def test_fails_low_line_coverage(self) -> None:
        unit = UnitTestResult(estimated_line_coverage=50.0, total_tests=10)
        assert _evaluate_quality(unit, _make_integration_result(), None) is False

    def test_fails_low_branch_coverage(self) -> None:
        unit = UnitTestResult(
            estimated_line_coverage=95.0,
            estimated_branch_coverage=50.0,
            total_tests=10,
        )
        # branch = 50 * 0.7 = 35 < 70
        assert _evaluate_quality(unit, _make_integration_result(), None) is False

    def test_fails_critical_security(self) -> None:
        assert (
            _evaluate_quality(
                _make_unit_result(), _make_integration_result(), _make_security_result_blocking()
            )
            is False
        )

    def test_fails_contract_tests(self) -> None:
        integration = IntegrationTestResult(total_tests=5, contract_tests_passed=False)
        assert _evaluate_quality(_make_unit_result(), integration, None) is False

    def test_passes_without_security_scan(self) -> None:
        assert _evaluate_quality(_make_unit_result(), _make_integration_result(), None) is True


# ── assemble_handoff ──────────────────────────────────────────────────


class TestAssembleHandoff:
    def test_basic_assembly(self) -> None:
        handoff = assemble_handoff(
            "proj-1", _make_unit_result(), _make_integration_result(), _make_security_result()
        )
        assert handoff.project_id == "proj-1"
        assert handoff.source_stage == "testing"
        assert handoff.target_stage == "deployment"
        assert handoff.quality_gate_passed is True

    def test_includes_security_findings(self) -> None:
        handoff = assemble_handoff(
            "proj-1", _make_unit_result(), _make_integration_result(), _make_security_result()
        )
        assert len(handoff.security_findings) == 1
        assert handoff.security_findings[0].category == "hardcoded-config"

    def test_includes_suite_results(self) -> None:
        handoff = assemble_handoff("proj-1", _make_unit_result(), _make_integration_result(), None)
        categories = [s.category for s in handoff.test_results]
        assert "unit" in categories
        assert "integration" in categories

    def test_gate_passed_reflects_quality(self) -> None:
        handoff = assemble_handoff(
            "proj-1",
            _make_unit_result(),
            _make_integration_result(),
            _make_security_result_blocking(),
        )
        assert handoff.quality_gate_passed is False

    def test_contract_deviations_mapped(self) -> None:
        integration = IntegrationTestResult(
            total_tests=5,
            contract_deviations=["Missing field: created_at"],
            contract_tests_passed=False,
        )
        handoff = assemble_handoff("proj-1", _make_unit_result(), integration, None)
        assert "Missing field: created_at" in handoff.contract_deviations

    def test_readiness_score_populated(self) -> None:
        handoff = assemble_handoff(
            "proj-1", _make_unit_result(), _make_integration_result(), _make_security_result()
        )
        assert 0 <= handoff.deploy_readiness_score <= 100


# ── _collect_blocking_issues ──────────────────────────────────────────


class TestCollectBlockingIssues:
    def test_no_issues_when_passing(self) -> None:
        issues = _collect_blocking_issues(
            _make_unit_result(), _make_integration_result(), _make_security_result()
        )
        assert issues == []

    def test_reports_critical_findings(self) -> None:
        issues = _collect_blocking_issues(
            _make_unit_result(), _make_integration_result(), _make_security_result_blocking()
        )
        assert any("CRITICAL" in i for i in issues)


# ── supervise_testing ─────────────────────────────────────────────────


class TestSuperviseTestingStage:
    @pytest.mark.asyncio
    async def test_produces_handoff(self, settings: object) -> None:
        impl = _make_impl_handoff()

        with (
            patch(
                "colette.stages.testing.supervisor.run_unit_tester",
                new_callable=AsyncMock,
                return_value=_make_unit_result(),
            ),
            patch(
                "colette.stages.testing.supervisor.run_integration_tester",
                new_callable=AsyncMock,
                return_value=_make_integration_result(),
            ),
            patch(
                "colette.stages.testing.supervisor.run_security_scanner",
                new_callable=AsyncMock,
                return_value=_make_security_result(),
            ),
        ):
            handoff = await supervise_testing(
                "proj-1",
                impl,
                settings=settings,  # type: ignore[arg-type]
            )

        assert handoff.project_id == "proj-1"
        assert handoff.quality_gate_passed is True
        assert handoff.deploy_readiness_score > 0

    @pytest.mark.asyncio
    async def test_continues_when_security_scanner_fails(self, settings: object) -> None:
        impl = _make_impl_handoff()

        with (
            patch(
                "colette.stages.testing.supervisor.run_unit_tester",
                new_callable=AsyncMock,
                return_value=_make_unit_result(),
            ),
            patch(
                "colette.stages.testing.supervisor.run_integration_tester",
                new_callable=AsyncMock,
                return_value=_make_integration_result(),
            ),
            patch(
                "colette.stages.testing.supervisor.run_security_scanner",
                new_callable=AsyncMock,
                side_effect=RuntimeError("LLM timeout"),
            ),
        ):
            handoff = await supervise_testing(
                "proj-1",
                impl,
                settings=settings,  # type: ignore[arg-type]
            )

        # Security scanner is SHOULD — failure doesn't block
        assert handoff.quality_gate_passed is True
        assert handoff.security_findings == []


# ── run_stage ─────────────────────────────────────────────────────────


class TestRunStage:
    @pytest.mark.asyncio
    async def test_raises_on_missing_implementation_handoff(self) -> None:
        state = {
            "project_id": "test-proj",
            "stage_statuses": {},
            "handoffs": {},
        }
        with pytest.raises(ValueError, match="requires a completed Implementation handoff"):
            await run_stage(state)

    @pytest.mark.asyncio
    async def test_produces_valid_state_update(self) -> None:
        impl = _make_impl_handoff()
        state = {
            "project_id": "test-proj",
            "stage_statuses": {},
            "handoffs": {
                StageName.IMPLEMENTATION.value: impl.to_dict(),
            },
        }

        with (
            patch(
                "colette.stages.testing.supervisor.run_unit_tester",
                new_callable=AsyncMock,
                return_value=_make_unit_result(),
            ),
            patch(
                "colette.stages.testing.supervisor.run_integration_tester",
                new_callable=AsyncMock,
                return_value=_make_integration_result(),
            ),
            patch(
                "colette.stages.testing.supervisor.run_security_scanner",
                new_callable=AsyncMock,
                return_value=_make_security_result(),
            ),
            patch("colette.stages.testing.stage.Settings"),
        ):
            result = await run_stage(state)

        assert result["current_stage"] == "testing"
        assert result["stage_statuses"]["testing"] == "completed"
        assert "testing" in result["handoffs"]
        handoff = result["handoffs"]["testing"]
        assert handoff["source_stage"] == "testing"
        assert len(result["progress_events"]) == 1

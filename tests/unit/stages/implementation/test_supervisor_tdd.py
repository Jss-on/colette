"""Tests for the implementation supervisor TDD workflow (Phase 2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from colette.schemas.common import GeneratedFile
from colette.schemas.module_design import (
    InterfaceContract,
    ModuleDesign,
    ModuleSpec,
    TestStrategy,
)
from colette.schemas.rework import ReworkDirective
from colette.stages.implementation.backend import BackendResult
from colette.stages.implementation.database import DatabaseResult
from colette.stages.implementation.frontend import FrontendResult
from colette.stages.implementation.refactor_agent import RefactorResult
from colette.stages.implementation.supervisor import (
    _apply_refactored,
    supervise_implementation,
)
from colette.stages.implementation.test_agent import TestGenerationResult
from colette.stages.implementation.verifier import VerificationReport

# ── Fixtures ──────────────────────────────────────────────────────────


def _file(path: str, content: str = "// ok", lang: str = "typescript") -> GeneratedFile:
    return GeneratedFile(path=path, content=content, language=lang)


def _frontend() -> FrontendResult:
    return FrontendResult(
        files=[_file("src/App.tsx")],
        packages=["react"],
        env_vars=["NEXT_PUBLIC_API_URL"],
    )


def _backend() -> BackendResult:
    return BackendResult(
        files=[_file("src/main.py", lang="python")],
        packages=["fastapi"],
        env_vars=["DATABASE_URL"],
        implemented_endpoints=["GET /api/v1/todos"],
    )


def _database() -> DatabaseResult:
    return DatabaseResult(
        files=[_file("migrations/001.sql", lang="sql")],
        packages=["alembic"],
        entities_created=["todos"],
    )


def _module_design() -> ModuleDesign:
    return ModuleDesign(
        work_item_id="WI-001",
        module_structure=[ModuleSpec(file_path="src/api.py", responsibility="API")],
        interfaces=[InterfaceContract(name="get", output_type="list")],
        test_strategy=TestStrategy(unit_test_targets=["get"]),
    )


def _test_gen_result() -> TestGenerationResult:
    return TestGenerationResult(
        test_files=[_file("tests/test_api.py", "def test(): pass", "python")],
        coverage_targets=["get"],
    )


def _clean_report() -> VerificationReport:
    return VerificationReport(
        findings=[],
        lint_passed=True,
        type_check_passed=True,
        build_passed=True,
        summary="OK",
    )


def _design_handoff():
    """Create a minimal DesignToImplementationHandoff."""
    from colette.schemas.design import DesignToImplementationHandoff

    return DesignToImplementationHandoff(
        project_id="test-proj",
        architecture_summary="Simple REST API",
        tech_stack={"backend": "fastapi", "frontend": "react", "database": "postgres"},
        openapi_spec="{}",
        endpoints=[],
        db_entities=[],
    )


# ── Tests: _apply_refactored ─────────────────────────────────────────


class TestApplyRefactored:
    def test_no_matching_files_returns_original(self) -> None:
        fe = _frontend()
        refactored = [_file("unrelated.py", "new")]
        result = _apply_refactored(fe, refactored)
        assert result is fe  # unchanged, same object

    def test_matching_files_replaced(self) -> None:
        fe = _frontend()
        refactored = [_file("src/App.tsx", "// refactored")]
        result = _apply_refactored(fe, refactored)
        assert result is not fe
        assert result.files[0].content == "// refactored"

    def test_backend_refactored(self) -> None:
        be = _backend()
        refactored = [_file("src/main.py", "# cleaned", "python")]
        result = _apply_refactored(be, refactored)
        assert result.files[0].content == "# cleaned"

    def test_preserves_non_matching_files(self) -> None:
        be = BackendResult(
            files=[_file("a.py", "old", "python"), _file("b.py", "keep", "python")],
            packages=[],
            env_vars=[],
            implemented_endpoints=[],
        )
        refactored = [_file("a.py", "new", "python")]
        result = _apply_refactored(be, refactored)
        assert result.files[0].content == "new"
        assert result.files[1].content == "keep"


# ── Tests: supervise_implementation TDD flow ──────────────────────────


@pytest.mark.asyncio
async def test_supervisor_calls_architect(settings: object) -> None:
    """Architect agent is called as the first step."""
    with (
        patch(
            "colette.stages.implementation.supervisor.run_architect",
            new_callable=AsyncMock,
            return_value=_module_design(),
        ) as mock_arch,
        patch(
            "colette.stages.implementation.supervisor.run_test_agent",
            new_callable=AsyncMock,
            return_value=_test_gen_result(),
        ),
        patch(
            "colette.stages.implementation.supervisor.run_frontend",
            new_callable=AsyncMock,
            return_value=_frontend(),
        ),
        patch(
            "colette.stages.implementation.supervisor.run_backend",
            new_callable=AsyncMock,
            return_value=_backend(),
        ),
        patch(
            "colette.stages.implementation.supervisor.run_database",
            new_callable=AsyncMock,
            return_value=_database(),
        ),
        patch(
            "colette.stages.implementation.supervisor.verify_and_fix_loop",
            new_callable=AsyncMock,
            return_value=(_frontend(), _backend(), _database(), _clean_report()),
        ),
        patch(
            "colette.stages.implementation.supervisor._run_cross_review",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        result = await supervise_implementation("proj-1", _design_handoff(), settings=settings)
        mock_arch.assert_awaited_once()
        assert result.handoff is not None


@pytest.mark.asyncio
async def test_supervisor_calls_test_agent(settings: object) -> None:
    """Test agent is called after architect."""
    with (
        patch(
            "colette.stages.implementation.supervisor.run_architect",
            new_callable=AsyncMock,
            return_value=_module_design(),
        ),
        patch(
            "colette.stages.implementation.supervisor.run_test_agent",
            new_callable=AsyncMock,
            return_value=_test_gen_result(),
        ) as mock_test,
        patch(
            "colette.stages.implementation.supervisor.run_frontend",
            new_callable=AsyncMock,
            return_value=_frontend(),
        ),
        patch(
            "colette.stages.implementation.supervisor.run_backend",
            new_callable=AsyncMock,
            return_value=_backend(),
        ),
        patch(
            "colette.stages.implementation.supervisor.run_database",
            new_callable=AsyncMock,
            return_value=_database(),
        ),
        patch(
            "colette.stages.implementation.supervisor.verify_and_fix_loop",
            new_callable=AsyncMock,
            return_value=(_frontend(), _backend(), _database(), _clean_report()),
        ),
        patch(
            "colette.stages.implementation.supervisor._run_cross_review",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        await supervise_implementation("proj-1", _design_handoff(), settings=settings)
        mock_test.assert_awaited_once()


@pytest.mark.asyncio
async def test_supervisor_with_rework_directive(settings: object) -> None:
    """Rework directive is passed through to architect and test agents."""
    directive = ReworkDirective(
        source_gate="impl_gate",
        target_stage="implementation",
        failure_reasons=["Type errors in backend"],
        attempt_number=2,
    )
    with (
        patch(
            "colette.stages.implementation.supervisor.run_architect",
            new_callable=AsyncMock,
            return_value=_module_design(),
        ) as mock_arch,
        patch(
            "colette.stages.implementation.supervisor.run_test_agent",
            new_callable=AsyncMock,
            return_value=_test_gen_result(),
        ) as mock_test,
        patch(
            "colette.stages.implementation.supervisor.run_frontend",
            new_callable=AsyncMock,
            return_value=_frontend(),
        ),
        patch(
            "colette.stages.implementation.supervisor.run_backend",
            new_callable=AsyncMock,
            return_value=_backend(),
        ),
        patch(
            "colette.stages.implementation.supervisor.run_database",
            new_callable=AsyncMock,
            return_value=_database(),
        ),
        patch(
            "colette.stages.implementation.supervisor.verify_and_fix_loop",
            new_callable=AsyncMock,
            return_value=(_frontend(), _backend(), _database(), _clean_report()),
        ),
        patch(
            "colette.stages.implementation.supervisor._run_cross_review",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        await supervise_implementation(
            "proj-1",
            _design_handoff(),
            settings=settings,
            rework_directive=directive,
        )
        # Architect should have been called with augmented context
        arch_call = mock_arch.call_args
        assert "Prior Attempt Context" in arch_call.args[0]
        # Test agent should have regression context
        test_call = mock_test.call_args
        assert test_call.kwargs["regression_context"] == "Type errors in backend"


@pytest.mark.asyncio
async def test_supervisor_architect_failure_graceful(settings: object) -> None:
    """If architect fails, supervisor continues without module design."""
    with (
        patch(
            "colette.stages.implementation.supervisor.run_architect",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM down"),
        ),
        patch(
            "colette.stages.implementation.supervisor.run_frontend",
            new_callable=AsyncMock,
            return_value=_frontend(),
        ),
        patch(
            "colette.stages.implementation.supervisor.run_backend",
            new_callable=AsyncMock,
            return_value=_backend(),
        ),
        patch(
            "colette.stages.implementation.supervisor.run_database",
            new_callable=AsyncMock,
            return_value=_database(),
        ),
        patch(
            "colette.stages.implementation.supervisor.verify_and_fix_loop",
            new_callable=AsyncMock,
            return_value=(_frontend(), _backend(), _database(), _clean_report()),
        ),
        patch(
            "colette.stages.implementation.supervisor._run_cross_review",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        result = await supervise_implementation("proj-1", _design_handoff(), settings=settings)
        # Should still produce a handoff
        assert result.handoff is not None


@pytest.mark.asyncio
async def test_supervisor_refactor_applied(settings: object) -> None:
    """Refactor agent results are merged into implementation files."""
    refactored = RefactorResult(
        refactored_files=[_file("src/App.tsx", "// refactored")],
        changes_made=["Cleaned up imports"],
    )
    with (
        patch(
            "colette.stages.implementation.supervisor.run_architect",
            new_callable=AsyncMock,
            return_value=_module_design(),
        ),
        patch(
            "colette.stages.implementation.supervisor.run_test_agent",
            new_callable=AsyncMock,
            return_value=_test_gen_result(),
        ),
        patch(
            "colette.stages.implementation.supervisor.run_frontend",
            new_callable=AsyncMock,
            return_value=_frontend(),
        ),
        patch(
            "colette.stages.implementation.supervisor.run_backend",
            new_callable=AsyncMock,
            return_value=_backend(),
        ),
        patch(
            "colette.stages.implementation.supervisor.run_database",
            new_callable=AsyncMock,
            return_value=_database(),
        ),
        patch(
            "colette.stages.implementation.supervisor.run_refactor",
            new_callable=AsyncMock,
            return_value=refactored,
        ),
        patch(
            "colette.stages.implementation.supervisor.verify_and_fix_loop",
            new_callable=AsyncMock,
            return_value=(_frontend(), _backend(), _database(), _clean_report()),
        ),
        patch(
            "colette.stages.implementation.supervisor._run_cross_review",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        result = await supervise_implementation("proj-1", _design_handoff(), settings=settings)
        assert result.handoff is not None

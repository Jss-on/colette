"""Tests for the implementation verify-and-fix loop (FR-IMP-012)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from colette.schemas.common import GeneratedFile, Severity
from colette.stages.implementation.backend import BackendResult
from colette.stages.implementation.database import DatabaseResult
from colette.stages.implementation.frontend import FrontendResult
from colette.stages.implementation.verifier import (
    VerificationFinding,
    VerificationReport,
    _agents_with_errors,
    _classify_file_owner,
    _replace_files,
    verify_and_fix_loop,
    verify_generated_code,
)

# ── Fixtures ──────────────────────────────────────────────────────────


def _file(path: str, content: str = "// ok", lang: str = "typescript") -> GeneratedFile:
    return GeneratedFile(path=path, content=content, language=lang)


def _frontend() -> FrontendResult:
    return FrontendResult(
        files=[_file("src/App.tsx"), _file("src/api/client.ts")],
        packages=["react"],
        env_vars=["NEXT_PUBLIC_API_URL"],
    )


def _backend() -> BackendResult:
    return BackendResult(
        files=[_file("src/routes/todos.py", lang="python"), _file("src/main.py", lang="python")],
        packages=["fastapi"],
        env_vars=["DATABASE_URL"],
        implemented_endpoints=["GET /api/v1/todos"],
    )


def _database() -> DatabaseResult:
    return DatabaseResult(
        files=[_file("migrations/001_init.sql", lang="sql")],
        packages=["alembic"],
        entities_created=["todos"],
    )


def _clean_report() -> VerificationReport:
    return VerificationReport(
        findings=[],
        lint_passed=True,
        type_check_passed=True,
        build_passed=True,
        summary="All checks passed.",
    )


def _failing_report(file_path: str = "src/routes/todos.py") -> VerificationReport:
    return VerificationReport(
        findings=[
            VerificationFinding(
                category="type",
                severity=Severity.HIGH,
                file_path=file_path,
                line=10,
                message="Undefined variable 'db_session'.",
                suggestion="Import db_session from database module.",
            ),
        ],
        lint_passed=True,
        type_check_passed=False,
        build_passed=True,
        summary="1 type error found.",
    )


# ── Unit tests: helper functions ──────────────────────────────────────


class TestClassifyFileOwner:
    def test_known_frontend_path(self) -> None:
        assert _classify_file_owner("src/App.tsx", {"src/App.tsx"}, set(), set()) == "frontend"

    def test_known_backend_path(self) -> None:
        assert _classify_file_owner("src/main.py", set(), {"src/main.py"}, set()) == "backend"

    def test_known_database_path(self) -> None:
        assert (
            _classify_file_owner("migrations/001.sql", set(), set(), {"migrations/001.sql"})
            == "database"
        )

    def test_heuristic_tsx(self) -> None:
        assert _classify_file_owner("src/component/Button.tsx", set(), set(), set()) == "frontend"

    def test_heuristic_migration(self) -> None:
        assert _classify_file_owner("migrations/002.sql", set(), set(), set()) == "database"

    def test_heuristic_default_backend(self) -> None:
        assert _classify_file_owner("src/utils.py", set(), set(), set()) == "backend"


class TestAgentsWithErrors:
    def test_identifies_backend(self) -> None:
        report = _failing_report("src/routes/todos.py")
        result = _agents_with_errors(report, set(), {"src/routes/todos.py"}, set())
        assert result == {"backend"}

    def test_multiple_agents(self) -> None:
        report = VerificationReport(
            findings=[
                VerificationFinding(
                    category="lint",
                    severity=Severity.MEDIUM,
                    file_path="src/App.tsx",
                    message="unused import",
                ),
                VerificationFinding(
                    category="type",
                    severity=Severity.HIGH,
                    file_path="src/main.py",
                    message="wrong type",
                ),
            ],
            lint_passed=False,
            type_check_passed=False,
            build_passed=True,
        )
        result = _agents_with_errors(report, {"src/App.tsx"}, {"src/main.py"}, set())
        assert result == {"frontend", "backend"}


class TestReplaceFiles:
    def test_replaces_by_path(self) -> None:
        original = [_file("a.py", "old"), _file("b.py", "keep")]
        fixed = [_file("a.py", "new")]
        merged = _replace_files(original, fixed)
        assert len(merged) == 2
        assert merged[0].content == "new"
        assert merged[1].content == "keep"

    def test_appends_new_files(self) -> None:
        original = [_file("a.py")]
        fixed = [_file("a.py", "fixed"), _file("c.py", "new")]
        merged = _replace_files(original, fixed)
        assert len(merged) == 2
        assert merged[1].path == "c.py"


# ── Unit tests: verify_generated_code ─────────────────────────────────


@pytest.mark.asyncio
async def test_verify_calls_invoke_structured(settings: object) -> None:
    report = _clean_report()
    with patch(
        "colette.stages.implementation.verifier.invoke_structured",
        new_callable=AsyncMock,
        return_value=report,
    ) as mock_invoke:
        result = await verify_generated_code([_file("a.py")], settings=settings)
        assert result.lint_passed is True
        mock_invoke.assert_awaited_once()


# ── Unit tests: verify_and_fix_loop ───────────────────────────────────


@pytest.mark.asyncio
async def test_loop_passes_on_first_try(settings: object) -> None:
    """When initial verification passes, no fix is attempted."""
    with (
        patch(
            "colette.stages.implementation.verifier.verify_generated_code",
            new_callable=AsyncMock,
            return_value=_clean_report(),
        ),
        patch(
            "colette.stages.implementation.verifier.fix_files",
            new_callable=AsyncMock,
        ) as mock_fix,
    ):
        _fe, _be, _db, report = await verify_and_fix_loop(
            _frontend(),
            _backend(),
            _database(),
            "design context",
            settings=settings,
            max_retries=3,
        )
        assert report.lint_passed is True
        mock_fix.assert_not_awaited()


@pytest.mark.asyncio
async def test_loop_fixes_on_retry(settings: object) -> None:
    """When first verification fails, fix is called and second passes."""
    failing = _failing_report("src/routes/todos.py")
    passing = _clean_report()

    with (
        patch(
            "colette.stages.implementation.verifier.verify_generated_code",
            new_callable=AsyncMock,
            side_effect=[failing, passing],
        ),
        patch(
            "colette.stages.implementation.verifier.fix_files",
            new_callable=AsyncMock,
            return_value=[_file("src/routes/todos.py", "fixed", "python")],
        ) as mock_fix,
    ):
        _fe, _be, _db, report = await verify_and_fix_loop(
            _frontend(),
            _backend(),
            _database(),
            "design context",
            settings=settings,
            max_retries=3,
        )
        assert report.lint_passed is True
        assert report.type_check_passed is True
        mock_fix.assert_awaited_once()


@pytest.mark.asyncio
async def test_loop_exhausts_retries(settings: object) -> None:
    """When all retries fail, returns final state with False flags."""
    failing = _failing_report("src/routes/todos.py")

    with (
        patch(
            "colette.stages.implementation.verifier.verify_generated_code",
            new_callable=AsyncMock,
            return_value=failing,
        ),
        patch(
            "colette.stages.implementation.verifier.fix_files",
            new_callable=AsyncMock,
            return_value=[_file("src/routes/todos.py", "still broken", "python")],
        ) as mock_fix,
    ):
        _fe, _be, _db, report = await verify_and_fix_loop(
            _frontend(),
            _backend(),
            _database(),
            "design context",
            settings=settings,
            max_retries=2,
        )
        assert report.type_check_passed is False
        assert mock_fix.await_count == 2


@pytest.mark.asyncio
async def test_loop_only_fixes_failing_agents(settings: object) -> None:
    """Only backend agent files are fixed when errors are in backend."""
    failing = _failing_report("src/main.py")
    passing = _clean_report()

    fix_calls: list[str] = []

    async def _track_fix(
        files: list[GeneratedFile], report: object, **kw: object
    ) -> list[GeneratedFile]:
        fix_calls.extend(f.path for f in files)
        return files

    with (
        patch(
            "colette.stages.implementation.verifier.verify_generated_code",
            new_callable=AsyncMock,
            side_effect=[failing, passing],
        ),
        patch(
            "colette.stages.implementation.verifier.fix_files",
            new_callable=AsyncMock,
            side_effect=_track_fix,
        ),
    ):
        await verify_and_fix_loop(
            _frontend(),
            _backend(),
            _database(),
            "design context",
            settings=settings,
            max_retries=3,
        )
        # Only backend files should be in fix_calls
        assert "src/routes/todos.py" in fix_calls
        assert "src/App.tsx" not in fix_calls
        assert "migrations/001_init.sql" not in fix_calls


@pytest.mark.asyncio
async def test_loop_handles_exception(settings: object) -> None:
    """If verification raises, the exception propagates (supervisor catches it)."""
    with (
        patch(
            "colette.stages.implementation.verifier.verify_generated_code",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM down"),
        ),
        pytest.raises(RuntimeError, match="LLM down"),
    ):
        await verify_and_fix_loop(
            _frontend(),
            _backend(),
            _database(),
            "design context",
            settings=settings,
            max_retries=3,
        )

"""LLM-based code verification and fix loop (FR-IMP-012).

After implementation agents generate code, this module:
1. Asks a VALIDATION-tier LLM to review for lint/type/build errors
2. If errors found, re-runs only the failing agent(s) with error context
3. Repeats up to ``max_retries`` times
4. Returns truthful lint/type/build flags for the implementation gate
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, Field

from colette.llm.structured import invoke_structured
from colette.schemas.agent_config import ModelTier
from colette.schemas.common import GeneratedFile, Severity
from colette.stages.implementation.prompts import (
    FIX_SYSTEM_PROMPT,
    VERIFICATION_SYSTEM_PROMPT,
)

if TYPE_CHECKING:
    from colette.config import Settings
    from colette.stages.implementation.backend import BackendResult
    from colette.stages.implementation.database import DatabaseResult
    from colette.stages.implementation.frontend import FrontendResult

logger = structlog.get_logger(__name__)


# ── Verification models ───────────────────────────────────────────────


class VerificationFinding(BaseModel, frozen=True):
    """A single issue found during code verification."""

    category: str = Field(description="'lint', 'type', or 'build'.")
    severity: Severity = Field(description="CRITICAL, HIGH, MEDIUM, or LOW.")
    file_path: str = Field(description="Path of the file with the issue.")
    line: int | None = Field(default=None, description="Line number, if known.")
    message: str = Field(description="Description of the error.")
    suggestion: str = Field(default="", description="How to fix.")


class VerificationReport(BaseModel, frozen=True):
    """Structured result of code verification."""

    findings: list[VerificationFinding] = Field(default_factory=list)
    lint_passed: bool = Field(default=True)
    type_check_passed: bool = Field(default=True)
    build_passed: bool = Field(default=True)
    summary: str = Field(default="")


# ── Fix result (reuses GeneratedFile list) ────────────────────────────


class FixResult(BaseModel, frozen=True):
    """Corrected files from the fix agent."""

    files: list[GeneratedFile] = Field(default_factory=list)


# ── Core functions ────────────────────────────────────────────────────


def _files_to_context(files: list[GeneratedFile], *, limit: int = 15) -> str:
    """Format generated files into a reviewable text block."""
    sections: list[str] = []
    for f in files[:limit]:
        sections.append(f"### {f.path}\n```{f.language}\n{f.content}\n```")
    if len(files) > limit:
        sections.append(f"\n... and {len(files) - limit} more files.")
    return "\n\n".join(sections)


async def verify_generated_code(
    files: list[GeneratedFile],
    *,
    settings: Settings,
) -> VerificationReport:
    """Ask the LLM to review generated files for lint/type/build errors."""
    context = _files_to_context(files)
    return await invoke_structured(
        system_prompt=VERIFICATION_SYSTEM_PROMPT,
        user_content=f"# Generated Source Files\n\n{context}",
        output_type=VerificationReport,
        settings=settings,
        model_tier=ModelTier.VALIDATION,
    )


async def fix_files(
    files: list[GeneratedFile],
    report: VerificationReport,
    *,
    settings: Settings,
) -> list[GeneratedFile]:
    """Ask the LLM to fix the specific errors in the given files."""
    code_context = _files_to_context(files)

    errors_text = "\n".join(
        f"- [{f.category}] {f.file_path}"
        + (f":{f.line}" if f.line else "")
        + f": {f.message}"
        + (f" — suggestion: {f.suggestion}" if f.suggestion else "")
        for f in report.findings
    )

    user_content = f"# Errors to Fix\n\n{errors_text}\n\n# Source Files\n\n{code_context}"

    result = await invoke_structured(
        system_prompt=FIX_SYSTEM_PROMPT,
        user_content=user_content,
        output_type=FixResult,
        settings=settings,
        model_tier=ModelTier.REASONING,
    )
    return result.files


def _classify_file_owner(
    path: str,
    frontend_paths: set[str],
    backend_paths: set[str],
    database_paths: set[str],
) -> str:
    """Determine which agent owns a file path."""
    if path in frontend_paths:
        return "frontend"
    if path in backend_paths:
        return "backend"
    if path in database_paths:
        return "database"
    # Heuristic fallback based on common patterns.
    lower = path.lower()
    if any(
        k in lower
        for k in (
            "src/app",
            "src/component",
            "src/page",
            "src/hook",
            "frontend/",
            "client/",
            ".tsx",
            ".jsx",
        )
    ):
        return "frontend"
    if any(k in lower for k in ("migration", "schema", "seed", "models/", "alembic", "prisma")):
        return "database"
    return "backend"


def _agents_with_errors(
    report: VerificationReport,
    frontend_paths: set[str],
    backend_paths: set[str],
    database_paths: set[str],
) -> set[str]:
    """Identify which agent(s) own the files with errors."""
    agents: set[str] = set()
    for finding in report.findings:
        agents.add(
            _classify_file_owner(finding.file_path, frontend_paths, backend_paths, database_paths)
        )
    return agents


def _replace_files(
    original: list[GeneratedFile],
    fixed: list[GeneratedFile],
) -> list[GeneratedFile]:
    """Merge fixed files into the original list (by path)."""
    fixed_map = {f.path: f for f in fixed}
    merged = [fixed_map.pop(f.path, f) for f in original]
    # Append any new files the fix agent added.
    merged.extend(fixed_map.values())
    return merged


async def verify_and_fix_loop(
    frontend: FrontendResult,
    backend: BackendResult,
    database: DatabaseResult,
    design_context: str,
    *,
    settings: Settings,
    max_retries: int = 3,
) -> tuple[FrontendResult, BackendResult, DatabaseResult, VerificationReport]:
    """Run verify → fix → verify loop, returning corrected agent results.

    Only the agent(s) whose files contain errors are re-invoked.
    If all retries are exhausted, returns the best result achieved.
    """
    from colette.stages.implementation.backend import BackendResult as _BackendResult
    from colette.stages.implementation.database import DatabaseResult as _DatabaseResult
    from colette.stages.implementation.frontend import FrontendResult as _FrontendResult

    frontend_paths = {f.path for f in frontend.files}
    backend_paths = {f.path for f in backend.files}
    database_paths = {f.path for f in database.files}

    all_files = [*frontend.files, *backend.files, *database.files]
    report = await verify_generated_code(all_files, settings=settings)

    logger.info(
        "verify_and_fix.initial",
        findings=len(report.findings),
        lint=report.lint_passed,
        types=report.type_check_passed,
        build=report.build_passed,
    )

    if report.lint_passed and report.type_check_passed and report.build_passed:
        return frontend, backend, database, report

    for attempt in range(1, max_retries + 1):
        failing = _agents_with_errors(report, frontend_paths, backend_paths, database_paths)
        logger.info(
            "verify_and_fix.attempt",
            attempt=attempt,
            max_retries=max_retries,
            failing_agents=sorted(failing),
            findings=len(report.findings),
        )

        # Fix files for each failing agent.
        for agent_name in failing:
            if agent_name == "frontend":
                fixed = await fix_files(frontend.files, report, settings=settings)
                merged = _replace_files(frontend.files, fixed)
                frontend = _FrontendResult(
                    files=merged,
                    packages=frontend.packages,
                    env_vars=frontend.env_vars,
                )
                frontend_paths = {f.path for f in frontend.files}
            elif agent_name == "backend":
                fixed = await fix_files(backend.files, report, settings=settings)
                merged = _replace_files(backend.files, fixed)
                backend = _BackendResult(
                    files=merged,
                    packages=backend.packages,
                    env_vars=backend.env_vars,
                    implemented_endpoints=backend.implemented_endpoints,
                )
                backend_paths = {f.path for f in backend.files}
            elif agent_name == "database":
                fixed = await fix_files(database.files, report, settings=settings)
                merged = _replace_files(database.files, fixed)
                database = _DatabaseResult(
                    files=merged,
                    packages=database.packages,
                    entities_created=database.entities_created,
                )
                database_paths = {f.path for f in database.files}

        # Re-verify.
        all_files = [*frontend.files, *backend.files, *database.files]
        report = await verify_generated_code(all_files, settings=settings)

        logger.info(
            "verify_and_fix.re_verified",
            attempt=attempt,
            findings=len(report.findings),
            lint=report.lint_passed,
            types=report.type_check_passed,
            build=report.build_passed,
        )

        if report.lint_passed and report.type_check_passed and report.build_passed:
            break

    logger.info(
        "verify_and_fix.complete",
        lint=report.lint_passed,
        types=report.type_check_passed,
        build=report.build_passed,
        total_findings=len(report.findings),
    )
    return frontend, backend, database, report

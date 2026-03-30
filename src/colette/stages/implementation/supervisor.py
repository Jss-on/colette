"""Implementation Supervisor — orchestrates frontend, backend, DB agents (FR-IMP-010/011)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, Field

from colette.llm.structured import invoke_structured
from colette.schemas.agent_config import ModelTier
from colette.schemas.common import EndpointSpec, FileDiff, GeneratedFile, Severity
from colette.schemas.design import DesignToImplementationHandoff
from colette.schemas.implementation import ImplementationToTestingHandoff
from colette.stages.implementation.backend import BackendResult, run_backend
from colette.stages.implementation.database import DatabaseResult, run_database
from colette.stages.implementation.frontend import FrontendResult, run_frontend
from colette.stages.implementation.prompts import CROSS_REVIEW_PROMPT

_MAX_SPEC_CHARS = 20_000

if TYPE_CHECKING:
    from colette.config import Settings

logger = structlog.get_logger(__name__)


# ── Result models for cross-review ──────────────────────────────────────


class ReviewFinding(BaseModel, frozen=True):
    """A single finding from cross-review (FR-IMP-011)."""

    severity: Severity = Field(description="CRITICAL, HIGH, MEDIUM, or LOW.")
    category: str = Field(description="E.g. 'API contract mismatch', 'type inconsistency'.")
    description: str
    location: str = Field(default="", description="File path or component reference.")


class CrossReviewResult(BaseModel, frozen=True):
    """Structured output from the cross-review step."""

    findings: list[ReviewFinding] = Field(default_factory=list)
    summary: str = Field(default="", description="Overall review summary.")


# ── Design-to-context conversion ────────────────────────────────────────


def _design_to_context(handoff: DesignToImplementationHandoff) -> str:
    """Convert the Design handoff into human-readable context for agents."""
    sections: list[str] = [
        f"# Architecture\n{handoff.architecture_summary}",
        "\n## Tech Stack",
    ]
    for role, tech in handoff.tech_stack.items():
        sections.append(f"- {role}: {tech}")

    if handoff.endpoints:
        sections.append("\n## API Endpoints")
        for ep in handoff.endpoints:
            auth = " [auth]" if ep.auth_required else ""
            sections.append(f"- {ep.method} {ep.path}: {ep.summary}{auth}")

    if handoff.openapi_spec:
        spec = handoff.openapi_spec[:_MAX_SPEC_CHARS]
        truncated = " (truncated)" if len(handoff.openapi_spec) > _MAX_SPEC_CHARS else ""
        sections.append(f"\n## OpenAPI Spec{truncated}\n```json\n{spec}\n```")

    if handoff.db_entities:
        sections.append("\n## Database Entities")
        for entity in handoff.db_entities:
            fields_str = ", ".join(f"{f['name']} ({f['type']})" for f in entity.fields)
            sections.append(f"- **{entity.name}**: {fields_str}")
            if entity.indexes:
                sections.append(f"  Indexes: {', '.join(entity.indexes)}")
            if entity.relationships:
                sections.append(f"  Relationships: {', '.join(entity.relationships)}")

    if handoff.migration_strategy:
        sections.append(f"\n## Migration Strategy\n{handoff.migration_strategy}")

    if handoff.ui_components:
        sections.append("\n## UI Components")
        for comp in handoff.ui_components:
            route = f" (route: {comp.route})" if comp.route else ""
            sections.append(f"- **{comp.name}**: {comp.description}{route}")

    if handoff.security_design:
        sections.append(f"\n## Security Design\n{handoff.security_design}")

    if handoff.tasks:
        sections.append("\n## Implementation Tasks")
        for task in handoff.tasks:
            deps = f" [depends: {', '.join(task.dependencies)}]" if task.dependencies else ""
            sections.append(f"- {task.id}: {task.description}{deps}")

    return "\n".join(sections)


# ── Quality evaluation ──────────────────────────────────────────────────


def _file_to_diff(f: GeneratedFile) -> FileDiff:
    """Convert a generated file into a FileDiff record."""
    return FileDiff(
        path=f.path,
        action="added",
        language=f.language,
        lines_added=f.content.count("\n") + 1,
    )


def _collect_files(
    frontend: FrontendResult,
    backend: BackendResult,
    database: DatabaseResult,
) -> list[FileDiff]:
    """Collect all generated files into FileDiff records."""
    all_files = [*frontend.files, *backend.files, *database.files]
    return [_file_to_diff(f) for f in all_files]


def _collect_env_vars(
    frontend: FrontendResult,
    backend: BackendResult,
) -> list[str]:
    """Merge environment variable names from frontend and backend (deduped)."""
    return list(dict.fromkeys([*frontend.env_vars, *backend.env_vars]))


def _parse_endpoints(
    backend: BackendResult,
    design: DesignToImplementationHandoff,
) -> list[EndpointSpec]:
    """Map backend implemented endpoints back to EndpointSpec from design."""
    design_endpoints = {f"{ep.method} {ep.path}": ep for ep in design.endpoints}
    matched: list[EndpointSpec] = []
    for ep_str in backend.implemented_endpoints:
        if ep_str in design_endpoints:
            matched.append(design_endpoints[ep_str])
    return matched


def _evaluate_quality(
    frontend: FrontendResult,
    backend: BackendResult,
    database: DatabaseResult,
    review: CrossReviewResult | None,
) -> bool:
    """Evaluate implementation quality gate.

    Passes when:
    - All three agents produced files
    - No CRITICAL cross-review findings
    """
    if not frontend.files or not backend.files or not database.files:
        return False

    if review:
        critical_count = sum(1 for f in review.findings if f.severity == Severity.CRITICAL)
        if critical_count > 0:
            return False

    return True


def _collect_test_hints(
    review: CrossReviewResult | None,
) -> list[str]:
    """Extract test hints from cross-review findings."""
    if not review:
        return []
    return [
        f"[{f.severity}] {f.category}: {f.description}"
        for f in review.findings
        if f.severity in {Severity.HIGH, Severity.MEDIUM}
    ]


# ── Cross-review ────────────────────────────────────────────────────────


async def _run_cross_review(
    frontend: FrontendResult,
    backend: BackendResult,
    *,
    settings: Settings,
) -> CrossReviewResult:
    """Cross-review frontend↔backend integration (FR-IMP-011).

    Backend reviews frontend API client; frontend reviews backend responses.
    """
    logger.info("cross_review.start")

    frontend_summary = "\n\n".join(
        f"### {f.path}\n```{f.language}\n{f.content}\n```"
        for f in frontend.files[:5]  # limit context
    )
    backend_summary = "\n\n".join(
        f"### {f.path}\n```{f.language}\n{f.content}\n```" for f in backend.files[:5]
    )
    user_content = (
        "# Frontend Code\n\n" + frontend_summary + "\n\n# Backend Code\n\n" + backend_summary
    )

    result = await invoke_structured(
        system_prompt=CROSS_REVIEW_PROMPT,
        user_content=user_content,
        output_type=CrossReviewResult,
        settings=settings,
        model_tier=ModelTier.EXECUTION,
    )

    logger.info(
        "cross_review.complete",
        findings=len(result.findings),
    )
    return result


# ── Handoff assembly ────────────────────────────────────────────────────


def assemble_handoff(
    project_id: str,
    design: DesignToImplementationHandoff,
    frontend: FrontendResult,
    backend: BackendResult,
    database: DatabaseResult,
    review: CrossReviewResult | None,
) -> ImplementationToTestingHandoff:
    """Assemble the Implementation-to-Testing handoff from agent outputs."""
    files = _collect_files(frontend, backend, database)
    env_vars = _collect_env_vars(frontend, backend)
    endpoints = _parse_endpoints(backend, design)
    gate_passed = _evaluate_quality(frontend, backend, database, review)
    test_hints = _collect_test_hints(review)

    return ImplementationToTestingHandoff(
        project_id=project_id,
        git_repo_url="",  # filled by git tool in real execution
        git_ref="main",
        files_changed=files,
        implemented_endpoints=endpoints,
        openapi_spec_ref=design.openapi_spec[:200] if design.openapi_spec else "",
        env_vars=env_vars,
        lint_passed=False,  # not yet run — Testing stage will verify
        type_check_passed=False,
        build_passed=False,
        test_hints=test_hints,
        quality_gate_passed=gate_passed,
    )


# ── Main supervisor ─────────────────────────────────────────────────────


async def supervise_implementation(
    project_id: str,
    design_handoff: DesignToImplementationHandoff,
    *,
    settings: Settings,
) -> ImplementationToTestingHandoff:
    """Orchestrate the Implementation stage (FR-IMP-*).

    Runs frontend, backend, and database agents, performs cross-review,
    then assembles the handoff to the Testing stage.
    """
    logger.info("implementation_supervisor.start", project_id=project_id)

    design_context = _design_to_context(design_handoff)

    # Run all three agents in parallel (FR-IMP-010)
    frontend, backend, database = await asyncio.gather(
        run_frontend(design_context, settings=settings),
        run_backend(design_context, settings=settings),
        run_database(design_context, settings=settings),
    )

    # Cross-review (FR-IMP-011, SHOULD — non-blocking on failure)
    review: CrossReviewResult | None = None
    try:
        review = await _run_cross_review(frontend, backend, settings=settings)
    except (ValueError, TimeoutError, RuntimeError) as exc:
        logger.warning("cross_review.failed", error_type=type(exc).__name__)

    handoff = assemble_handoff(
        project_id,
        design_handoff,
        frontend,
        backend,
        database,
        review,
    )

    logger.info(
        "implementation_supervisor.complete",
        project_id=project_id,
        files=len(handoff.files_changed),
        endpoints=len(handoff.implemented_endpoints),
        gate_passed=handoff.quality_gate_passed,
    )
    return handoff

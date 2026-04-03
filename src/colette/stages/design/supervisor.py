"""Design Supervisor — orchestrates architect, API, UI designers (FR-DES-006)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import structlog

from colette.schemas.base import DEFAULT_MAX_HANDOFF_CHARS
from colette.schemas.common import TaskComplexity
from colette.schemas.design import DesignToImplementationHandoff, ImplementationTask
from colette.schemas.requirements import RequirementsToDesignHandoff
from colette.stages.design.api_designer import APIDesignResult, run_api_designer
from colette.stages.design.architect import ArchitectureResult, run_architect
from colette.stages.design.ui_designer import UIDesignResult, run_ui_designer

if TYPE_CHECKING:
    from colette.config import Settings

logger = structlog.get_logger(__name__)


def _prd_to_text(handoff: RequirementsToDesignHandoff) -> str:
    """Convert PRD handoff to human-readable text for specialist agents."""
    sections: list[str] = [
        f"# {handoff.project_overview}",
        "\n## Functional Requirements",
    ]
    for story in handoff.functional_requirements:
        sections.append(
            f"\n### {story.id}: {story.title}\n"
            f"As a {story.persona}, I want to {story.goal}, "
            f"so that {story.benefit}.\n"
            f"Priority: {story.priority}\n"
            "Acceptance Criteria:\n" + "\n".join(f"- {c}" for c in story.acceptance_criteria)
        )
    if handoff.nonfunctional_requirements:
        sections.append("\n## Non-Functional Requirements")
        for nfr in handoff.nonfunctional_requirements:
            target = f" (target: {nfr.target})" if nfr.target else ""
            sections.append(f"- [{nfr.id}] {nfr.category}: {nfr.description}{target}")
    if handoff.tech_constraints:
        sections.append("\n## Technical Constraints")
        for tc in handoff.tech_constraints:
            sections.append(f"- [{tc.id}] {tc.description} ({tc.rationale})")
    return "\n".join(sections)


def _generate_tasks(
    arch: ArchitectureResult,
    api: APIDesignResult,
    ui: UIDesignResult,
) -> list[ImplementationTask]:
    """Generate implementation tasks from design outputs (FR-DES-006)."""
    tasks: list[ImplementationTask] = []
    task_id = 1

    # Scaffolding task
    tasks.append(
        ImplementationTask(
            id=f"TASK-{task_id:03d}",
            description="Set up project scaffolding and build system",
            complexity=TaskComplexity.MEDIUM,
            assigned_agent="backend_dev",
        )
    )
    task_id += 1

    # DB migration tasks
    for entity in arch.db_entities:
        tasks.append(
            ImplementationTask(
                id=f"TASK-{task_id:03d}",
                description=f"Create database migration for '{entity.name}' entity",
                complexity=TaskComplexity.SMALL,
                dependencies=["TASK-001"],
                assigned_agent="db_engineer",
            )
        )
        task_id += 1

    # API endpoint tasks
    for ep in api.endpoints:
        tasks.append(
            ImplementationTask(
                id=f"TASK-{task_id:03d}",
                description=f"Implement {ep.method} {ep.path}: {ep.summary}",
                complexity=TaskComplexity.MEDIUM,
                dependencies=["TASK-001"],
                assigned_agent="backend_dev",
            )
        )
        task_id += 1

    # Frontend component tasks
    for comp in ui.ui_components:
        tasks.append(
            ImplementationTask(
                id=f"TASK-{task_id:03d}",
                description=f"Implement '{comp.name}' component: {comp.description}",
                complexity=TaskComplexity.MEDIUM,
                assigned_agent="frontend_dev",
            )
        )
        task_id += 1

    return tasks


def _evaluate_design_quality(
    arch: ArchitectureResult,
    api: APIDesignResult,
) -> bool:
    """Derive quality gate status from actual design outputs."""
    return (
        bool(arch.architecture_summary)
        and bool(arch.tech_stack)
        and bool(arch.db_entities)
        and bool(api.openapi_spec)
        and bool(api.endpoints)
    )


_MAX_OPENAPI_SPEC_CHARS = 20_000
_MAX_ARCH_SUMMARY_CHARS = 8_000
_MAX_SECURITY_DESIGN_CHARS = 4_000

# Leave headroom below the hard limit for base-class fields added during
# Pydantic construction (created_at, metadata, schema_version, etc.).
_SIZE_BUDGET = DEFAULT_MAX_HANDOFF_CHARS - 5_000


def _estimate_fields_size(fields: dict[str, Any]) -> int:
    """Estimate the JSON size of handoff fields before Pydantic construction."""

    def _convert(v: Any) -> Any:
        if isinstance(v, list):
            return [_convert(item) for item in v]
        if hasattr(v, "model_dump"):
            return v.model_dump(mode="json")
        return v

    return len(json.dumps({k: _convert(v) for k, v in fields.items()}, default=str))


def _truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... (truncated)"


def assemble_handoff(
    project_id: str,
    arch: ArchitectureResult,
    api: APIDesignResult,
    ui: UIDesignResult,
) -> DesignToImplementationHandoff:
    """Assemble the Design-to-Implementation handoff from specialist outputs.

    Large text fields are truncated to keep the handoff within size limits.
    If the total still exceeds the budget after initial truncation, structured
    lists are progressively trimmed (endpoints carry the same data as the raw
    ``openapi_spec``, so the spec is sacrificed first).
    """
    tasks = _generate_tasks(arch, api, ui)
    gate_passed = _evaluate_design_quality(arch, api)

    # Mutable copies so we can truncate progressively.
    fields: dict[str, Any] = {
        "project_id": project_id,
        "architecture_summary": _truncate_text(arch.architecture_summary, _MAX_ARCH_SUMMARY_CHARS),
        "tech_stack": arch.tech_stack,
        "openapi_spec": _truncate_text(api.openapi_spec, _MAX_OPENAPI_SPEC_CHARS),
        "endpoints": list(api.endpoints),
        "db_entities": list(arch.db_entities),
        "migration_strategy": arch.migration_strategy,
        "ui_components": list(ui.ui_components),
        "navigation_flows": list(ui.navigation_flows),
        "adrs": list(arch.adrs),
        "security_design": _truncate_text(arch.security_design, _MAX_SECURITY_DESIGN_CHARS),
        "tasks": tasks,
        "quality_gate_passed": gate_passed,
    }

    size = _estimate_fields_size(fields)

    # ── Progressive truncation phases ─────────────────────────────────
    if size > _SIZE_BUDGET:
        logger.warning("design_handoff.truncating", phase=1, size=size, budget=_SIZE_BUDGET)
        fields["openapi_spec"] = _truncate_text(fields["openapi_spec"], 2_000)
        size = _estimate_fields_size(fields)

    if size > _SIZE_BUDGET:
        logger.warning("design_handoff.truncating", phase=2, size=size)
        fields["endpoints"] = fields["endpoints"][:15]
        fields["db_entities"] = fields["db_entities"][:10]
        fields["ui_components"] = fields["ui_components"][:10]
        size = _estimate_fields_size(fields)

    if size > _SIZE_BUDGET:
        logger.warning("design_handoff.truncating", phase=3, size=size)
        fields["architecture_summary"] = _truncate_text(fields["architecture_summary"], 3_000)
        fields["security_design"] = _truncate_text(fields["security_design"], 1_000)
        fields["adrs"] = fields["adrs"][:5]

    return DesignToImplementationHandoff(**fields)


async def supervise_design(
    project_id: str,
    prd_handoff: RequirementsToDesignHandoff,
    *,
    settings: Settings,
) -> DesignToImplementationHandoff:
    """Orchestrate the Design stage (FR-DES-*).

    Runs the architect first (provides context), then the API designer
    and UI designer sequentially (could be parallelised in future).
    """
    logger.info("design_supervisor.start", project_id=project_id)

    prd_text = _prd_to_text(prd_handoff)

    # Architect runs first — API and UI designers depend on the architecture
    arch = await run_architect(prd_text, settings=settings)

    # API and UI designers use the architecture as context
    api = await run_api_designer(prd_text, arch.architecture_summary, settings=settings)
    ui = await run_ui_designer(prd_text, arch.architecture_summary, settings=settings)

    handoff = assemble_handoff(project_id, arch, api, ui)

    logger.info(
        "design_supervisor.complete",
        project_id=project_id,
        endpoints=len(handoff.endpoints),
        entities=len(handoff.db_entities),
        components=len(handoff.ui_components),
        tasks=len(handoff.tasks),
    )
    return handoff

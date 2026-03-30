"""Design Supervisor — orchestrates architect, API, UI designers (FR-DES-006)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

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
            "Acceptance Criteria:\n"
            + "\n".join(f"- {c}" for c in story.acceptance_criteria)
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


def assemble_handoff(
    project_id: str,
    arch: ArchitectureResult,
    api: APIDesignResult,
    ui: UIDesignResult,
) -> DesignToImplementationHandoff:
    """Assemble the Design-to-Implementation handoff from specialist outputs."""
    tasks = _generate_tasks(arch, api, ui)

    return DesignToImplementationHandoff(
        project_id=project_id,
        architecture_summary=arch.architecture_summary,
        tech_stack=arch.tech_stack,
        openapi_spec=api.openapi_spec,
        endpoints=api.endpoints,
        db_entities=arch.db_entities,
        migration_strategy=arch.migration_strategy,
        ui_components=ui.ui_components,
        navigation_flows=ui.navigation_flows,
        adrs=arch.adrs,
        security_design=arch.security_design,
        tasks=tasks,
        quality_gate_passed=True,
    )


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

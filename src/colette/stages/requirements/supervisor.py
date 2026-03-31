"""Requirements Supervisor — orchestrates analyst + researcher (FR-REQ-006/007)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from colette.schemas.common import UserStory
from colette.schemas.requirements import RequirementsToDesignHandoff
from colette.stages.requirements.analyst import AnalysisResult, run_analyst
from colette.stages.requirements.researcher import ResearchResult, run_researcher

if TYPE_CHECKING:
    from colette.config import Settings

logger = structlog.get_logger(__name__)


def _ensure_story_ids(stories: list[UserStory]) -> list[UserStory]:
    """Ensure all user stories have proper US-REQ-{NNN} IDs (FR-REQ-007)."""
    result: list[UserStory] = []
    for idx, story in enumerate(stories, start=1):
        if not story.id.startswith("US-REQ-"):
            story = story.model_copy(update={"id": f"US-REQ-{idx:03d}"})
        result.append(story)
    return result


def _compute_completeness(analysis: AnalysisResult) -> float:
    """Compute adjusted completeness score (FR-REQ-006).

    Starts from the analyst's self-assessed score and applies
    penalties for missing or low-quality content.
    """
    penalties = 0.0

    if not analysis.user_stories:
        penalties += 0.3
    elif len(analysis.user_stories) < 3:
        penalties += 0.1

    if not analysis.nfrs:
        penalties += 0.1

    excess_questions = max(0, len(analysis.open_questions) - 5)
    penalties += 0.02 * min(excess_questions, 4)

    stories_without_criteria = sum(1 for s in analysis.user_stories if not s.acceptance_criteria)
    if stories_without_criteria > 0:
        penalties += 0.1

    return max(0.0, min(1.0, analysis.completeness_score - penalties))


def assemble_handoff(
    project_id: str,
    analysis: AnalysisResult,
    research: ResearchResult | None,
) -> RequirementsToDesignHandoff:
    """Assemble the Requirements-to-Design handoff from specialist outputs."""
    stories = _ensure_story_ids(analysis.user_stories)

    # Merge tech constraints from analyst and researcher (immutable)
    existing_ids = {c.id for c in analysis.tech_constraints}
    constraints = list(analysis.tech_constraints) + [
        c for c in (research.suggested_constraints if research else []) if c.id not in existing_ids
    ]

    completeness = _compute_completeness(analysis)

    return RequirementsToDesignHandoff(
        project_id=project_id,
        project_overview=analysis.project_overview,
        functional_requirements=stories,
        nonfunctional_requirements=analysis.nfrs,
        tech_constraints=constraints,
        assumptions=analysis.assumptions,
        out_of_scope=analysis.out_of_scope,
        completeness_score=completeness,
        open_questions=analysis.open_questions,
        quality_gate_passed=completeness >= 0.80,
    )


async def supervise_requirements(
    project_id: str,
    user_request: str,
    *,
    settings: Settings,
) -> RequirementsToDesignHandoff:
    """Orchestrate the Requirements stage (FR-REQ-*).

    Runs the analyst (MUST) and researcher (SHOULD, non-blocking on failure),
    then assembles and validates the handoff.
    """
    logger.info("requirements_supervisor.start", project_id=project_id)

    # Analyst is mandatory
    analysis = await run_analyst(user_request, settings=settings)

    # Researcher is optional (FR-REQ-004 is SHOULD)
    research: ResearchResult | None = None
    try:
        research = await run_researcher(user_request, settings=settings)
    except (ValueError, TimeoutError, RuntimeError) as exc:
        logger.warning("researcher.failed", error_type=type(exc).__name__)

    handoff = assemble_handoff(project_id, analysis, research)

    logger.info(
        "requirements_supervisor.complete",
        project_id=project_id,
        stories=len(handoff.functional_requirements),
        completeness=handoff.completeness_score,
        gate_passed=handoff.quality_gate_passed,
    )
    return handoff

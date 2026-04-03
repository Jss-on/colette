"""Planning agent — decomposes user request into structured work items (Phase 3)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, Field

from colette.llm.structured import invoke_structured
from colette.schemas.agent_config import ModelTier
from colette.schemas.backlog import WorkItem

if TYPE_CHECKING:
    from colette.config import Settings

logger = structlog.get_logger(__name__)

PLANNING_SYSTEM_PROMPT = """\
You are the Planning Agent in the Colette multi-agent SDLC system.

Given a project description, decompose it into structured work items.

## Rules

1. Each work item must have a clear, actionable title and description.
2. Assign realistic priorities based on user impact and dependencies.
3. Include specific, testable acceptance criteria for each item.
4. Set stage_scope to the SDLC stages this item affects \
(requirements, design, implementation, testing, deployment, monitoring).
5. Identify dependencies between work items.
6. Categorize items as feature, bug, improvement, tech_debt, or spike.

## Output

Return a list of WorkItem objects. Each should have:
- A unique ID (format: WI-NNN)
- type, title, description, priority
- acceptance_criteria (at least one per item)
- stage_scope (which pipeline stages are involved)
- depends_on (IDs of items that must complete first)\
"""


class PlanningResult(BaseModel, frozen=True):
    """Structured output from the planning agent."""

    work_items: list[WorkItem] = Field(default_factory=list)
    project_summary: str = Field(default="", description="Brief summary of the project.")
    estimated_sprints: int = Field(default=1, ge=1, description="Estimated number of sprints.")


async def run_planning_agent(
    user_request: str,
    *,
    settings: Settings,
) -> PlanningResult:
    """Decompose a user request into structured work items."""
    logger.info("planning_agent.start")

    result = await invoke_structured(
        system_prompt=PLANNING_SYSTEM_PROMPT,
        user_content=f"Project Description:\n\n{user_request}",
        output_type=PlanningResult,
        settings=settings,
        model_tier=ModelTier.PLANNING,
    )

    logger.info(
        "planning_agent.complete",
        work_items=len(result.work_items),
        estimated_sprints=result.estimated_sprints,
    )
    return result

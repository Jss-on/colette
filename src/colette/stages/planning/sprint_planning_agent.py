"""Sprint planning agent — selects work items for the next sprint (Phase 4)."""

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

SPRINT_PLANNING_PROMPT = """\
You are the Sprint Planning Agent in the Colette multi-agent SDLC system.

Given a backlog of work items, select items for the next sprint.

## Rules

1. Respect priority ordering (P0 first, then P1, P2, P3).
2. Respect dependencies — don't select an item whose dependency isn't done.
3. Limit sprint scope to what can be completed in one pipeline run.
4. Generate a clear sprint goal summarizing the sprint's focus.
5. Consider prior sprint context when available.

## Output

Return the selected work item IDs and a sprint goal.\
"""


class SprintPlanningResult(BaseModel, frozen=True):
    """Structured output from sprint planning."""

    selected_item_ids: list[str] = Field(default_factory=list)
    sprint_goal: str = Field(default="")
    rationale: str = Field(default="")


async def run_sprint_planning(
    backlog_items: list[WorkItem],
    *,
    settings: Settings,
    prior_sprint_context: str = "",
) -> SprintPlanningResult:
    """Select work items from the backlog for the next sprint."""
    logger.info("sprint_planning.start", items=len(backlog_items))

    items_desc = "\n".join(
        f"- [{i.id}] {i.title} (P:{i.priority}, deps:{i.depends_on})" for i in backlog_items
    )

    user_parts = [f"## Backlog Items\n\n{items_desc}"]
    if prior_sprint_context:
        user_parts.append(f"\n## Prior Sprint Context\n\n{prior_sprint_context}")

    result = await invoke_structured(
        system_prompt=SPRINT_PLANNING_PROMPT,
        user_content="\n".join(user_parts),
        output_type=SprintPlanningResult,
        settings=settings,
        model_tier=ModelTier.PLANNING,
    )

    logger.info(
        "sprint_planning.complete",
        selected=len(result.selected_item_ids),
        goal=result.sprint_goal[:80],
    )
    return result

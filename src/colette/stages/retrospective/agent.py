"""Retrospective agent — analyzes sprint metrics and suggests improvements (Phase 6)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from colette.llm.structured import invoke_structured
from colette.schemas.agent_config import ModelTier
from colette.schemas.retrospective import SprintRetrospective

if TYPE_CHECKING:
    from colette.config import Settings

logger = structlog.get_logger(__name__)

RETROSPECTIVE_PROMPT = """\
You are the Retrospective Agent in the Colette multi-agent SDLC system.

After a sprint completes, analyze the sprint metrics and produce a \
retrospective with actionable improvements.

## Analysis Areas

1. **Rework patterns**: Which stages needed the most rework? Why?
2. **Token efficiency**: Which stages consumed the most tokens?
3. **Gate performance**: Which gates had the lowest scores?
4. **Human interventions**: How many times did humans override agent decisions?
5. **Scope changes**: What changed during the sprint?

## Output

Produce a SprintRetrospective with:
- Quantitative metrics (rework counts, token usage, gate scores)
- Qualitative improvements (actionable recommendations)
- Config adjustments (threshold changes, model tier upgrades)\
"""


async def run_retrospective(
    sprint_id: str,
    sprint_metrics: dict[str, object],
    *,
    settings: Settings,
) -> SprintRetrospective:
    """Analyze sprint metrics and produce a retrospective."""
    logger.info("retrospective_agent.start", sprint_id=sprint_id)

    user_content = f"## Sprint {sprint_id} Metrics\n\n"
    for key, value in sprint_metrics.items():
        user_content += f"- **{key}**: {value}\n"

    result = await invoke_structured(
        system_prompt=RETROSPECTIVE_PROMPT,
        user_content=user_content,
        output_type=SprintRetrospective,
        settings=settings,
        model_tier=ModelTier.VALIDATION,
    )

    logger.info(
        "retrospective_agent.complete",
        sprint_id=sprint_id,
        improvements=len(result.improvements),
        adjustments=len(result.config_adjustments),
    )
    return result

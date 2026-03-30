"""Domain Researcher agent — domain research and context (FR-REQ-004)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, Field

from colette.llm.structured import invoke_structured
from colette.schemas.agent_config import ModelTier
from colette.schemas.common import TechConstraint
from colette.stages.requirements.prompts import RESEARCHER_SYSTEM_PROMPT

if TYPE_CHECKING:
    from colette.config import Settings

logger = structlog.get_logger(__name__)


class ResearchResult(BaseModel, frozen=True):
    """Structured output from the Domain Researcher."""

    domain_insights: str
    suggested_constraints: list[TechConstraint] = Field(default_factory=list)
    relevant_standards: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)


async def run_researcher(user_request: str, *, settings: Settings) -> ResearchResult:
    """Research domain context for the project (FR-REQ-004).

    This is a SHOULD requirement — the pipeline continues even if
    the researcher fails.

    Parameters
    ----------
    user_request:
        Natural language project description.
    settings:
        Application settings for LLM configuration.

    Returns
    -------
    ResearchResult
        Domain context to enrich the requirements.
    """
    logger.info("researcher.start", request_length=len(user_request))

    result = await invoke_structured(
        system_prompt=RESEARCHER_SYSTEM_PROMPT,
        user_content=f"Research domain context for:\n\n{user_request}",
        output_type=ResearchResult,
        settings=settings,
        model_tier=ModelTier.EXECUTION,
    )

    logger.info(
        "researcher.complete",
        constraints=len(result.suggested_constraints),
        standards=len(result.relevant_standards),
    )
    return result

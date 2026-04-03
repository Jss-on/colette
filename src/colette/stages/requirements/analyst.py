"""Requirements Analyst agent — NL input to structured PRD (FR-REQ-001/003)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, Field

from colette.llm.structured import invoke_structured
from colette.schemas.agent_config import ModelTier
from colette.schemas.common import NFRSpec, TechConstraint, UserStory
from colette.stages.requirements.prompts import ANALYST_SYSTEM_PROMPT

if TYPE_CHECKING:
    from colette.config import Settings

logger = structlog.get_logger(__name__)


class AnalysisResult(BaseModel, frozen=True):
    """Structured output from the Requirements Analyst."""

    project_overview: str
    user_stories: list[UserStory]
    nfrs: list[NFRSpec] = Field(default_factory=list)
    tech_constraints: list[TechConstraint] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    completeness_score: float = Field(ge=0.0, le=1.0)
    open_questions: list[str] = Field(default_factory=list)


async def run_analyst(user_request: str, *, settings: Settings) -> AnalysisResult:
    """Analyze NL input and produce structured requirements (FR-REQ-001/003).

    Parameters
    ----------
    user_request:
        Natural language project description from the user.
    settings:
        Application settings for LLM configuration.

    Returns
    -------
    AnalysisResult
        Structured PRD content ready for supervisor assembly.
    """
    logger.info("analyst.start", request_length=len(user_request))

    result = await invoke_structured(
        system_prompt=ANALYST_SYSTEM_PROMPT,
        user_content=f"Project Description:\n\n{user_request}",
        output_type=AnalysisResult,
        settings=settings,
        model_tier=ModelTier.PLANNING,
    )

    logger.info(
        "analyst.complete",
        stories=len(result.user_stories),
        nfrs=len(result.nfrs),
        completeness=result.completeness_score,
    )
    return result

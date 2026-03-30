"""API Designer agent — OpenAPI 3.1 spec generation (FR-DES-002/008)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, Field

from colette.llm.structured import invoke_structured
from colette.schemas.agent_config import ModelTier
from colette.schemas.common import EndpointSpec
from colette.stages.design.prompts import API_DESIGNER_SYSTEM_PROMPT

if TYPE_CHECKING:
    from colette.config import Settings

logger = structlog.get_logger(__name__)


class APIDesignResult(BaseModel, frozen=True):
    """Structured output from the API Designer."""

    openapi_spec: str = Field(description="Full OpenAPI 3.1 JSON string.")
    endpoints: list[EndpointSpec] = Field(default_factory=list)


async def run_api_designer(
    prd_text: str,
    architecture_summary: str,
    *,
    settings: Settings,
) -> APIDesignResult:
    """Design REST API from PRD and architecture (FR-DES-002).

    Parameters
    ----------
    prd_text:
        Human-readable PRD text.
    architecture_summary:
        Architecture summary from the System Architect.
    settings:
        Application settings for LLM configuration.
    """
    logger.info("api_designer.start")

    context = (
        f"Product Requirements Document:\n\n{prd_text}\n\n"
        f"Architecture Summary:\n\n{architecture_summary}"
    )

    result = await invoke_structured(
        system_prompt=API_DESIGNER_SYSTEM_PROMPT,
        user_content=context,
        output_type=APIDesignResult,
        settings=settings,
        model_tier=ModelTier.EXECUTION,
    )

    logger.info("api_designer.complete", endpoints=len(result.endpoints))
    return result

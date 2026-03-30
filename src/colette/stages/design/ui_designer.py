"""UI/UX Designer agent — component specs and navigation (FR-DES-004)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, Field

from colette.llm.structured import invoke_structured
from colette.schemas.agent_config import ModelTier
from colette.schemas.common import ComponentSpec
from colette.stages.design.prompts import UI_DESIGNER_SYSTEM_PROMPT

if TYPE_CHECKING:
    from colette.config import Settings

logger = structlog.get_logger(__name__)


class UIDesignResult(BaseModel, frozen=True):
    """Structured output from the UI Designer."""

    ui_components: list[ComponentSpec] = Field(default_factory=list)
    navigation_flows: list[str] = Field(default_factory=list)


async def run_ui_designer(
    prd_text: str,
    architecture_summary: str,
    *,
    settings: Settings,
) -> UIDesignResult:
    """Design UI components from PRD and architecture (FR-DES-004).

    Parameters
    ----------
    prd_text:
        Human-readable PRD text.
    architecture_summary:
        Architecture summary from the System Architect.
    settings:
        Application settings for LLM configuration.
    """
    logger.info("ui_designer.start")

    context = (
        f"Product Requirements Document:\n\n{prd_text}\n\n"
        f"Architecture Summary:\n\n{architecture_summary}"
    )

    result = await invoke_structured(
        system_prompt=UI_DESIGNER_SYSTEM_PROMPT,
        user_content=context,
        output_type=UIDesignResult,
        settings=settings,
        model_tier=ModelTier.EXECUTION,
    )

    logger.info(
        "ui_designer.complete",
        components=len(result.ui_components),
        flows=len(result.navigation_flows),
    )
    return result

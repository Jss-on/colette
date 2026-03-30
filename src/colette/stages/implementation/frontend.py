"""Frontend Developer agent — React/Next.js code generation (FR-IMP-001)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, Field

from colette.llm.structured import invoke_structured
from colette.schemas.agent_config import ModelTier
from colette.schemas.common import GeneratedFile
from colette.stages.implementation.prompts import FRONTEND_SYSTEM_PROMPT

if TYPE_CHECKING:
    from colette.config import Settings

logger = structlog.get_logger(__name__)


class FrontendResult(BaseModel, frozen=True):
    """Structured output from the Frontend Developer agent."""

    files: list[GeneratedFile] = Field(default_factory=list)
    packages: list[str] = Field(
        default_factory=list,
        description="npm package names required (e.g. ['react-hook-form', 'zustand']).",
    )
    env_vars: list[str] = Field(
        default_factory=list,
        description="Required environment variable names.",
    )
    notes: str = Field(
        default="",
        description="Implementation notes or caveats.",
    )


async def run_frontend(
    design_context: str,
    *,
    settings: Settings,
) -> FrontendResult:
    """Generate frontend code from design artifacts (FR-IMP-001).

    Uses the EXECUTION model tier (Sonnet) for code generation.
    """
    logger.info("frontend_dev.start")

    result = await invoke_structured(
        system_prompt=FRONTEND_SYSTEM_PROMPT,
        user_content=f"Design Specification:\n\n{design_context}",
        output_type=FrontendResult,
        settings=settings,
        model_tier=ModelTier.EXECUTION,
    )

    logger.info(
        "frontend_dev.complete",
        files=len(result.files),
        packages=len(result.packages),
    )
    return result

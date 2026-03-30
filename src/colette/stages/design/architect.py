"""System Architect agent — architecture, tech stack, ADRs (FR-DES-001/005/007)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, Field

from colette.llm.structured import invoke_structured
from colette.schemas.agent_config import ModelTier
from colette.schemas.common import ADRRecord, EntitySpec
from colette.stages.design.prompts import ARCHITECT_SYSTEM_PROMPT

if TYPE_CHECKING:
    from colette.config import Settings

logger = structlog.get_logger(__name__)


class ArchitectureResult(BaseModel, frozen=True):
    """Structured output from the System Architect."""

    architecture_summary: str
    tech_stack: dict[str, str]
    db_entities: list[EntitySpec] = Field(default_factory=list)
    adrs: list[ADRRecord] = Field(default_factory=list)
    security_design: str = ""
    migration_strategy: str = ""


async def run_architect(prd_text: str, *, settings: Settings) -> ArchitectureResult:
    """Design system architecture from PRD (FR-DES-001/003/005/007).

    Uses the PLANNING model tier (Opus) for deep architectural reasoning.
    """
    logger.info("architect.start")

    result = await invoke_structured(
        system_prompt=ARCHITECT_SYSTEM_PROMPT,
        user_content=f"Product Requirements Document:\n\n{prd_text}",
        output_type=ArchitectureResult,
        settings=settings,
        model_tier=ModelTier.PLANNING,
    )

    logger.info(
        "architect.complete",
        tech_stack_keys=list(result.tech_stack.keys()),
        entities=len(result.db_entities),
        adrs=len(result.adrs),
    )
    return result

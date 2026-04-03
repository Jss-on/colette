"""Architect agent — produces ModuleDesign before code generation (Phase 2)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from colette.llm.structured import invoke_structured
from colette.schemas.agent_config import ModelTier
from colette.schemas.module_design import ModuleDesign
from colette.stages.implementation.prompts import ARCHITECT_SYSTEM_PROMPT

if TYPE_CHECKING:
    from colette.config import Settings

logger = structlog.get_logger(__name__)


async def run_architect(
    design_context: str,
    *,
    settings: Settings,
    prior_design: ModuleDesign | None = None,
) -> ModuleDesign:
    """Produce a module-level design from the design specification.

    When *prior_design* is provided (rework), the architect refines it
    rather than starting from scratch.
    """
    logger.info("architect_agent.start")

    user_parts: list[str] = [f"Design Specification:\n\n{design_context}"]

    if prior_design is not None:
        user_parts.append(
            "\n\n## Prior Module Design (refine, do not discard)\n\n"
            f"Modules: {[m.file_path for m in prior_design.module_structure]}\n"
            f"Interfaces: {[i.name for i in prior_design.interfaces]}\n"
            f"Decisions: {prior_design.design_decisions}\n"
            f"Complexity: {prior_design.complexity_estimate}"
        )

    result = await invoke_structured(
        system_prompt=ARCHITECT_SYSTEM_PROMPT,
        user_content="\n".join(user_parts),
        output_type=ModuleDesign,
        settings=settings,
        model_tier=ModelTier.PLANNING,
    )

    logger.info(
        "architect_agent.complete",
        modules=len(result.module_structure),
        interfaces=len(result.interfaces),
        complexity=result.complexity_estimate,
    )
    return result

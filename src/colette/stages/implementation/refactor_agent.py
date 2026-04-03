"""Refactor agent — TDD REFACTOR phase: cleans code after tests pass (Phase 2)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, Field

from colette.llm.structured import invoke_structured
from colette.schemas.agent_config import ModelTier
from colette.schemas.common import GeneratedFile
from colette.stages.implementation.prompts import REFACTOR_SYSTEM_PROMPT

if TYPE_CHECKING:
    from colette.config import Settings

logger = structlog.get_logger(__name__)


class RefactorResult(BaseModel, frozen=True):
    """Structured output from the refactor agent."""

    refactored_files: list[GeneratedFile] = Field(default_factory=list)
    changes_made: list[str] = Field(
        default_factory=list,
        description="Summary of refactoring changes applied.",
    )
    notes: str = Field(default="", description="Refactoring notes.")


async def run_refactor(
    implementation_files: list[GeneratedFile],
    test_files: list[GeneratedFile],
    *,
    settings: Settings,
) -> RefactorResult:
    """Apply clean-code refactoring to implementation code (TDD REFACTOR phase).

    Receives the implementation files and their passing test files, then
    returns refactored versions of only the files that changed.
    """
    logger.info("refactor_agent.start", files=len(implementation_files))

    impl_summary = "\n\n".join(
        f"### {f.path}\n```{f.language}\n{f.content}\n```" for f in implementation_files[:10]
    )
    test_summary = "\n\n".join(
        f"### {f.path}\n```{f.language}\n{f.content}\n```" for f in test_files[:5]
    )

    user_content = (
        "# Implementation Code\n\n"
        + impl_summary
        + "\n\n# Test Code (must still pass)\n\n"
        + test_summary
    )

    result = await invoke_structured(
        system_prompt=REFACTOR_SYSTEM_PROMPT,
        user_content=user_content,
        output_type=RefactorResult,
        settings=settings,
        model_tier=ModelTier.EXECUTION,
    )

    logger.info(
        "refactor_agent.complete",
        refactored=len(result.refactored_files),
        changes=len(result.changes_made),
    )
    return result

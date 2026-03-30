"""CI/CD Engineer agent — pipeline generation and rollback (FR-DEP-003/005/006/008)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, Field

from colette.llm.structured import invoke_structured
from colette.schemas.agent_config import ModelTier
from colette.schemas.common import GeneratedFile
from colette.stages.deployment.prompts import CICD_ENGINEER_SYSTEM_PROMPT

if TYPE_CHECKING:
    from colette.config import Settings

logger = structlog.get_logger(__name__)


class CICDResult(BaseModel, frozen=True):
    """Structured output from the CI/CD Engineer agent."""

    pipeline_files: list[GeneratedFile] = Field(default_factory=list)
    platform: str = Field(
        default="github_actions",
        description="CI/CD platform (github_actions, gitlab_ci).",
    )
    stages: list[str] = Field(
        default_factory=list,
        description="Pipeline stage names in execution order.",
    )
    has_rollback: bool = Field(
        default=False,
        description="Whether automated rollback is configured.",
    )
    rollback_command: str = Field(
        default="",
        description="Command or strategy for manual rollback.",
    )
    staging_auto_deploy: bool = Field(
        default=False,
        description="Whether staging deploys automatically after gates pass.",
    )
    production_gate: bool = Field(
        default=False,
        description="Whether production requires manual approval.",
    )
    notes: str = Field(default="", description="Implementation notes or caveats.")


async def run_cicd_engineer(
    deployment_context: str,
    *,
    settings: Settings,
) -> CICDResult:
    """Generate CI/CD pipeline configurations (FR-DEP-003/005/006/008).

    Uses the EXECUTION model tier (Sonnet) for pipeline generation.
    """
    logger.info("cicd_engineer.start")

    result = await invoke_structured(
        system_prompt=CICD_ENGINEER_SYSTEM_PROMPT,
        user_content=f"Project & Test Results:\n\n{deployment_context}",
        output_type=CICDResult,
        settings=settings,
        model_tier=ModelTier.EXECUTION,
    )

    logger.info(
        "cicd_engineer.complete",
        files=len(result.pipeline_files),
        stages=len(result.stages),
        has_rollback=result.has_rollback,
    )
    return result

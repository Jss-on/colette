"""Backend Developer agent — route handlers, auth, business logic (FR-IMP-002/004)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, Field

from colette.llm.structured import invoke_structured
from colette.schemas.agent_config import ModelTier
from colette.schemas.common import GeneratedFile
from colette.stages.implementation.prompts import BACKEND_SYSTEM_PROMPT

if TYPE_CHECKING:
    from colette.config import Settings

logger = structlog.get_logger(__name__)


class BackendResult(BaseModel, frozen=True):
    """Structured output from the Backend Developer agent."""

    files: list[GeneratedFile] = Field(default_factory=list)
    packages: list[str] = Field(
        default_factory=list,
        description="Package dependencies (e.g. ['fastapi', 'pyjwt', 'bcrypt']).",
    )
    env_vars: list[str] = Field(
        default_factory=list,
        description="Required environment variable names (not values).",
    )
    implemented_endpoints: list[str] = Field(
        default_factory=list,
        description="List of 'METHOD /path' strings for implemented endpoints.",
    )
    auth_strategy: str = Field(
        default="",
        description="Authentication strategy implemented (e.g. 'JWT with bcrypt').",
    )
    notes: str = Field(
        default="",
        description="Implementation notes or caveats.",
    )


async def run_backend(
    design_context: str,
    *,
    settings: Settings,
) -> BackendResult:
    """Generate backend code from design artifacts (FR-IMP-002/004).

    Uses the EXECUTION model tier (Sonnet) for code generation.
    """
    logger.info("backend_dev.start")

    result = await invoke_structured(
        system_prompt=BACKEND_SYSTEM_PROMPT,
        user_content=f"Design Specification:\n\n{design_context}",
        output_type=BackendResult,
        settings=settings,
        model_tier=ModelTier.EXECUTION,
    )

    logger.info(
        "backend_dev.complete",
        files=len(result.files),
        endpoints=len(result.implemented_endpoints),
    )
    return result

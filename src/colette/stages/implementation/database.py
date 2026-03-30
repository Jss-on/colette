"""Database Engineer agent — ORM models, migrations, seed data (FR-IMP-003)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, Field

from colette.llm.structured import invoke_structured
from colette.schemas.agent_config import ModelTier
from colette.schemas.common import GeneratedFile
from colette.stages.implementation.prompts import DATABASE_SYSTEM_PROMPT

if TYPE_CHECKING:
    from colette.config import Settings

logger = structlog.get_logger(__name__)


class DatabaseResult(BaseModel, frozen=True):
    """Structured output from the Database Engineer agent."""

    files: list[GeneratedFile] = Field(default_factory=list)
    packages: list[str] = Field(
        default_factory=list,
        description="Package dependencies (e.g. ['sqlalchemy', 'alembic']).",
    )
    entities_created: list[str] = Field(
        default_factory=list,
        description="Entity/table names created.",
    )
    migrations: list[str] = Field(
        default_factory=list,
        description="Migration file paths in application order.",
    )
    seed_data_included: bool = Field(
        default=False,
        description="Whether seed data was generated.",
    )
    notes: str = Field(
        default="",
        description="Implementation notes or caveats.",
    )


async def run_database(
    design_context: str,
    *,
    settings: Settings,
) -> DatabaseResult:
    """Generate database code from design artifacts (FR-IMP-003).

    Uses the EXECUTION model tier (Sonnet) for code generation.
    """
    logger.info("db_engineer.start")

    result = await invoke_structured(
        system_prompt=DATABASE_SYSTEM_PROMPT,
        user_content=f"Design Specification:\n\n{design_context}",
        output_type=DatabaseResult,
        settings=settings,
        model_tier=ModelTier.EXECUTION,
    )

    logger.info(
        "db_engineer.complete",
        files=len(result.files),
        entities=len(result.entities_created),
        migrations=len(result.migrations),
    )
    return result

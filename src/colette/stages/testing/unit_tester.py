"""Unit Tester agent — test generation with coverage estimation (FR-TST-001/002)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, Field

from colette.llm.structured import invoke_structured
from colette.schemas.agent_config import ModelTier
from colette.schemas.common import GeneratedFile
from colette.stages.testing.prompts import UNIT_TESTER_SYSTEM_PROMPT

if TYPE_CHECKING:
    from colette.config import Settings

logger = structlog.get_logger(__name__)


class UnitTestResult(BaseModel, frozen=True):
    """Structured output from the Unit Tester agent."""

    test_files: list[GeneratedFile] = Field(default_factory=list)
    framework: str = Field(
        default="pytest",
        description="Test framework used (pytest, jest, vitest).",
    )
    total_tests: int = Field(default=0, ge=0)
    estimated_line_coverage: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Estimated line coverage percentage.",
    )
    estimated_branch_coverage: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Estimated branch coverage percentage.",
    )
    test_categories: list[str] = Field(
        default_factory=list,
        description="Categories of tests generated (e.g. unit, property-based).",
    )
    notes: str = Field(default="", description="Implementation notes or caveats.")


async def run_unit_tester(
    implementation_context: str,
    *,
    settings: Settings,
) -> UnitTestResult:
    """Generate unit tests from implementation artifacts (FR-TST-001/002).

    Uses the EXECUTION model tier (Sonnet) for test generation.
    """
    logger.info("unit_tester.start")

    result = await invoke_structured(
        system_prompt=UNIT_TESTER_SYSTEM_PROMPT,
        user_content=f"Implementation Code:\n\n{implementation_context}",
        output_type=UnitTestResult,
        settings=settings,
        model_tier=ModelTier.EXECUTION,
    )

    logger.info(
        "unit_tester.complete",
        files=len(result.test_files),
        total_tests=result.total_tests,
        line_coverage=result.estimated_line_coverage,
    )
    return result

"""Test agent — TDD RED phase: generates failing tests from ModuleDesign (Phase 2)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, Field

from colette.llm.structured import invoke_structured
from colette.schemas.agent_config import ModelTier
from colette.schemas.common import GeneratedFile
from colette.schemas.module_design import ModuleDesign
from colette.stages.implementation.prompts import TEST_AGENT_SYSTEM_PROMPT

if TYPE_CHECKING:
    from colette.config import Settings

logger = structlog.get_logger(__name__)


class TestGenerationResult(BaseModel, frozen=True):
    """Structured output from the test generation agent."""

    test_files: list[GeneratedFile] = Field(default_factory=list)
    coverage_targets: list[str] = Field(
        default_factory=list,
        description="Interfaces/functions these tests target.",
    )
    notes: str = Field(default="", description="Test strategy notes.")


async def run_test_agent(
    module_design: ModuleDesign,
    acceptance_criteria: list[str],
    *,
    settings: Settings,
    regression_context: str = "",
) -> TestGenerationResult:
    """Generate test files from a ModuleDesign (TDD RED phase).

    When *regression_context* is provided (rework), extra tests are
    generated to cover the prior failure scenario.
    """
    logger.info("test_agent.start")

    user_parts: list[str] = [
        "## Module Design\n",
        f"Modules: {len(module_design.module_structure)}",
    ]
    for mod in module_design.module_structure:
        user_parts.append(f"- {mod.file_path}: {mod.responsibility}")
        user_parts.append(f"  Public API: {mod.public_api}")

    user_parts.append("\n## Interface Contracts\n")
    for iface in module_design.interfaces:
        user_parts.append(f"- {iface.name}({iface.input_types}) -> {iface.output_type}")
        if iface.preconditions:
            user_parts.append(f"  Pre: {iface.preconditions}")
        if iface.postconditions:
            user_parts.append(f"  Post: {iface.postconditions}")

    user_parts.append("\n## Test Strategy\n")
    user_parts.append(f"Unit targets: {module_design.test_strategy.unit_test_targets}")
    user_parts.append(
        f"Integration targets: {module_design.test_strategy.integration_test_targets}"
    )
    user_parts.append(f"Edge cases: {module_design.test_strategy.edge_cases}")

    if acceptance_criteria:
        user_parts.append("\n## Acceptance Criteria\n")
        for ac in acceptance_criteria:
            user_parts.append(f"- {ac}")

    if regression_context:
        user_parts.append("\n## Regression Context (from prior failure)\n")
        user_parts.append(regression_context)
        user_parts.append("Add regression tests covering this failure scenario.")

    result = await invoke_structured(
        system_prompt=TEST_AGENT_SYSTEM_PROMPT,
        user_content="\n".join(user_parts),
        output_type=TestGenerationResult,
        settings=settings,
        model_tier=ModelTier.EXECUTION,
    )

    logger.info(
        "test_agent.complete",
        test_files=len(result.test_files),
        coverage_targets=len(result.coverage_targets),
    )
    return result

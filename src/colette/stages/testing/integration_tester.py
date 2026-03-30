"""Integration Tester agent — API, contract, and E2E tests (FR-TST-003/004/005)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, Field

from colette.llm.structured import invoke_structured
from colette.schemas.agent_config import ModelTier
from colette.schemas.common import GeneratedFile
from colette.stages.testing.prompts import INTEGRATION_TESTER_SYSTEM_PROMPT

if TYPE_CHECKING:
    from colette.config import Settings

logger = structlog.get_logger(__name__)


class IntegrationTestResult(BaseModel, frozen=True):
    """Structured output from the Integration Tester agent."""

    test_files: list[GeneratedFile] = Field(default_factory=list)
    framework: str = Field(
        default="httpx",
        description="Test framework used (httpx, supertest, playwright).",
    )
    total_tests: int = Field(default=0, ge=0)
    endpoint_coverage: list[str] = Field(
        default_factory=list,
        description="Endpoints tested as 'METHOD /path' strings.",
    )
    contract_deviations: list[str] = Field(
        default_factory=list,
        description="OpenAPI contract deviations found.",
    )
    contract_tests_passed: bool = Field(
        default=False,
        description="True if all responses conform to OpenAPI spec.",
    )
    e2e_flows_tested: list[str] = Field(
        default_factory=list,
        description="User flow names covered by E2E stubs.",
    )
    notes: str = Field(default="", description="Implementation notes or caveats.")


async def run_integration_tester(
    implementation_context: str,
    *,
    settings: Settings,
) -> IntegrationTestResult:
    """Generate integration and contract tests (FR-TST-003/004/005).

    Uses the EXECUTION model tier (Sonnet) for test generation.
    """
    logger.info("integration_tester.start")

    result = await invoke_structured(
        system_prompt=INTEGRATION_TESTER_SYSTEM_PROMPT,
        user_content=f"Implementation Code & API Spec:\n\n{implementation_context}",
        output_type=IntegrationTestResult,
        settings=settings,
        model_tier=ModelTier.EXECUTION,
    )

    logger.info(
        "integration_tester.complete",
        files=len(result.test_files),
        total_tests=result.total_tests,
        endpoints=len(result.endpoint_coverage),
        contract_passed=result.contract_tests_passed,
    )
    return result

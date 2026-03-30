"""Security Scanner agent — SAST, dependency audit, accessibility (FR-TST-006/007/010)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, Field

from colette.llm.structured import invoke_structured
from colette.schemas.agent_config import ModelTier
from colette.schemas.common import SecurityFinding
from colette.stages.testing.prompts import SECURITY_SCANNER_SYSTEM_PROMPT

if TYPE_CHECKING:
    from colette.config import Settings

logger = structlog.get_logger(__name__)


class SecurityScanResult(BaseModel, frozen=True):
    """Structured output from the Security Scanner agent."""

    findings: list[SecurityFinding] = Field(default_factory=list)
    dependency_vulnerabilities: list[SecurityFinding] = Field(
        default_factory=list,
        description="CVE findings from dependency audit.",
    )
    accessibility_issues: list[str] = Field(
        default_factory=list,
        description="WCAG 2.1 A/AA violations found.",
    )
    sast_tool: str = Field(
        default="semgrep",
        description="SAST tool used or emulated.",
    )
    has_blocking_findings: bool = Field(
        default=False,
        description="True if any HIGH or CRITICAL finding exists.",
    )
    summary: str = Field(default="", description="Overall security assessment.")


async def run_security_scanner(
    implementation_context: str,
    test_context: str,
    *,
    settings: Settings,
) -> SecurityScanResult:
    """Perform security analysis on implementation and test code (FR-TST-006/007/010).

    Uses the VALIDATION model tier (Haiku) as this is a scanner/validator role.
    """
    logger.info("security_scanner.start")

    user_content = (
        f"Implementation Code:\n\n{implementation_context}\n\nTest Code:\n\n{test_context}"
    )

    result = await invoke_structured(
        system_prompt=SECURITY_SCANNER_SYSTEM_PROMPT,
        user_content=user_content,
        output_type=SecurityScanResult,
        settings=settings,
        model_tier=ModelTier.VALIDATION,
    )

    logger.info(
        "security_scanner.complete",
        findings=len(result.findings),
        dep_vulns=len(result.dependency_vulnerabilities),
        blocking=result.has_blocking_findings,
    )
    return result

"""Triage agent — classifies bug scope and determines pipeline entry point (Phase 5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, Field

from colette.llm.structured import invoke_structured
from colette.schemas.agent_config import ModelTier

if TYPE_CHECKING:
    from colette.config import Settings
    from colette.schemas.bug import BugReport

logger = structlog.get_logger(__name__)

TRIAGE_PROMPT = """\
You are the Triage Agent in the Colette multi-agent SDLC system.

Given a bug report, classify where in the pipeline the root cause lies \
and determine which stages need to be re-run.

## Scope Classification

- **requirements**: Missing or ambiguous requirements caused the bug.
  → Re-run full pipeline.
- **design**: Architectural or API design flaw caused the bug.
  → Skip requirements, re-run design + implementation + testing + deployment.
- **implementation**: Code-level bug in implementation.
  → Skip requirements + design, re-run implementation + testing + deployment.
- **testing**: Missing test coverage allowed the bug to reach production.
  → Re-run testing only.

## Output

Return the classified scope, recommended skip_stages, and a brief \
root cause analysis.\
"""

# Stages to skip based on scope classification.
_SKIP_MAP: dict[str, list[str]] = {
    "requirements": [],
    "design": ["requirements"],
    "implementation": ["requirements", "design"],
    "testing": ["requirements", "design", "implementation", "deployment", "monitoring"],
}


class TriageResult(BaseModel, frozen=True):
    """Structured output from the triage agent."""

    scope: str = Field(description="requirements | design | implementation | testing")
    root_cause_analysis: str = Field(default="")
    skip_stages: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


async def run_triage(
    bug_report: BugReport,
    *,
    settings: Settings,
) -> TriageResult:
    """Classify a bug report and determine pipeline re-run scope."""
    logger.info("triage_agent.start", bug_id=bug_report.id)

    user_content = (
        f"## Bug Report\n\n"
        f"**Title**: {bug_report.title}\n"
        f"**Description**: {bug_report.description}\n"
        f"**Severity**: {bug_report.severity}\n"
    )
    if bug_report.reproduction_steps:
        user_content += "\n**Reproduction Steps**:\n"
        for step in bug_report.reproduction_steps:
            user_content += f"- {step}\n"

    result = await invoke_structured(
        system_prompt=TRIAGE_PROMPT,
        user_content=user_content,
        output_type=TriageResult,
        settings=settings,
        model_tier=ModelTier.VALIDATION,
    )

    # Override skip_stages from the map if scope is recognized.
    skip_stages = _SKIP_MAP.get(result.scope, [])
    result = TriageResult(
        scope=result.scope,
        root_cause_analysis=result.root_cause_analysis,
        skip_stages=skip_stages,
        confidence=result.confidence,
    )

    logger.info(
        "triage_agent.complete",
        scope=result.scope,
        skip_stages=result.skip_stages,
    )
    return result

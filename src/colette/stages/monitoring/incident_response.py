"""Incident Response Agent — alerts, runbooks, incident procedures (FR-MON-004/006/007)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, Field

from colette.llm.structured import invoke_structured
from colette.schemas.agent_config import ModelTier
from colette.schemas.common import GeneratedFile
from colette.stages.monitoring.prompts import INCIDENT_RESPONSE_AGENT_SYSTEM_PROMPT

if TYPE_CHECKING:
    from colette.config import Settings

logger = structlog.get_logger(__name__)


class AlertRule(BaseModel, frozen=True):
    """A structured alert rule definition (FR-MON-004)."""

    name: str = Field(description="Alert rule name (e.g. 'HighErrorRate').")
    condition: str = Field(description="Condition expression (e.g. 'error_rate > 0.05').")
    threshold: str = Field(description="Threshold value (e.g. '5%', '500ms').")
    duration: str = Field(description="Duration before firing (e.g. '5m', '60s').")
    severity: str = Field(description="Alert severity: critical, warning, info.")
    action: str = Field(description="Action on fire (e.g. 'page', 'notify', 'auto-scale').")


class IncidentResponseResult(BaseModel, frozen=True):
    """Structured output from the Incident Response Agent."""

    alert_rules: list[GeneratedFile] = Field(
        default_factory=list,
        description="Prometheus/AlertManager rule configuration files.",
    )
    runbooks: list[GeneratedFile] = Field(
        default_factory=list,
        description="Operational runbook markdown files.",
    )
    incident_procedures: list[GeneratedFile] = Field(
        default_factory=list,
        description="Incident response procedure and RCA template files.",
    )
    alert_rule_definitions: list[AlertRule] = Field(
        default_factory=list,
        description="Structured alert rule definitions for programmatic use.",
    )
    notes: str = Field(default="", description="Implementation notes or caveats.")


async def run_incident_response(
    deployment_context: str,
    *,
    settings: Settings,
) -> IncidentResponseResult:
    """Generate incident response configurations (FR-MON-004/006/007).

    Uses the EXECUTION model tier (Sonnet) for configuration generation.
    """
    logger.info("incident_response.start")

    result = await invoke_structured(
        system_prompt=INCIDENT_RESPONSE_AGENT_SYSTEM_PROMPT,
        user_content=f"Deployment context:\n\n{deployment_context}",
        output_type=IncidentResponseResult,
        settings=settings,
        model_tier=ModelTier.VALIDATION,
    )

    logger.info(
        "incident_response.complete",
        alert_rules=len(result.alert_rules),
        runbooks=len(result.runbooks),
        incident_procedures=len(result.incident_procedures),
        alert_rule_definitions=len(result.alert_rule_definitions),
    )
    return result

"""Observability Agent — logging, metrics, dashboards, health, SLOs (FR-MON-001..008)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, Field

from colette.llm.structured import invoke_structured
from colette.schemas.agent_config import ModelTier
from colette.schemas.common import GeneratedFile
from colette.stages.monitoring.prompts import OBSERVABILITY_AGENT_SYSTEM_PROMPT

if TYPE_CHECKING:
    from colette.config import Settings

logger = structlog.get_logger(__name__)


class SLODefinition(BaseModel, frozen=True):
    """A Service Level Objective definition (FR-MON-008)."""

    name: str = Field(description="SLO name (e.g. 'availability', 'latency-p99').")
    target: str = Field(description="Target value (e.g. '99.9%', '<500ms').")
    metric: str = Field(description="Prometheus metric or expression to evaluate.")
    window: str = Field(default="30d", description="Evaluation window (e.g. '30d', '7d').")


class ObservabilityResult(BaseModel, frozen=True):
    """Structured output from the Observability Agent."""

    logging_configs: list[GeneratedFile] = Field(
        default_factory=list,
        description="Structured JSON logging configuration files.",
    )
    prometheus_configs: list[GeneratedFile] = Field(
        default_factory=list,
        description="Prometheus metrics endpoint and scrape configuration files.",
    )
    grafana_dashboards: list[GeneratedFile] = Field(
        default_factory=list,
        description="Grafana dashboard JSON provisioning files.",
    )
    health_endpoints: list[GeneratedFile] = Field(
        default_factory=list,
        description="Health check endpoint implementation files.",
    )
    slo_definitions: list[SLODefinition] = Field(
        default_factory=list,
        description="SLO definitions derived from NFRs and deployment targets.",
    )
    notes: str = Field(default="", description="Implementation notes or caveats.")


async def run_observability_agent(
    deployment_context: str,
    *,
    settings: Settings,
) -> ObservabilityResult:
    """Generate observability configurations (FR-MON-001/002/003/005/008).

    Uses the EXECUTION model tier (Sonnet) for configuration generation.
    """
    logger.info("observability_agent.start")

    result = await invoke_structured(
        system_prompt=OBSERVABILITY_AGENT_SYSTEM_PROMPT,
        user_content=f"Deployment context:\n\n{deployment_context}",
        output_type=ObservabilityResult,
        settings=settings,
        model_tier=ModelTier.EXECUTION,
    )

    logger.info(
        "observability_agent.complete",
        logging_configs=len(result.logging_configs),
        prometheus_configs=len(result.prometheus_configs),
        grafana_dashboards=len(result.grafana_dashboards),
        health_endpoints=len(result.health_endpoints),
        slo_definitions=len(result.slo_definitions),
    )
    return result

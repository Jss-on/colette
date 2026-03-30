"""Monitoring Supervisor — orchestrates observability and incident response agents (FR-MON-*)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import structlog
from pydantic import BaseModel, Field

from colette.schemas.common import GeneratedFile
from colette.schemas.deployment import DeploymentToMonitoringHandoff
from colette.stages.monitoring.incident_response import (
    AlertRule,
    IncidentResponseResult,
    run_incident_response,
)
from colette.stages.monitoring.observability_agent import (
    ObservabilityResult,
    SLODefinition,
    run_observability_agent,
)

if TYPE_CHECKING:
    from colette.config import Settings

logger = structlog.get_logger(__name__)


# ── Result model ────────────────────────────────────────────────────────


class MonitoringResult(BaseModel, frozen=True):
    """Final result of the Monitoring stage (terminal — no outgoing handoff)."""

    deployment_id: str = Field(description="Deployment identifier from upstream handoff.")
    generated_files: list[GeneratedFile] = Field(
        default_factory=list,
        description="All generated files from both agents combined.",
    )
    slo_definitions: list[SLODefinition] = Field(
        default_factory=list,
        description="SLO definitions from observability agent.",
    )
    alert_rules: list[AlertRule] = Field(
        default_factory=list,
        description="Alert rule definitions from incident response agent.",
    )
    quality_gate_passed: bool = Field(
        default=False,
        description="Whether the monitoring quality gate passed.",
    )
    notes: str = Field(default="", description="Summary notes from the supervisor.")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict with JSON-safe values."""
        return self.model_dump()


# ── Deployment-to-context conversion ────────────────────────────────────


def _deployment_to_context(handoff: DeploymentToMonitoringHandoff) -> str:
    """Convert the Deployment handoff into human-readable context for monitoring agents."""
    sections: list[str] = ["# Deployment Context for Monitoring"]

    sections.append(f"\n## Deployment ID: {handoff.deployment_id}")
    sections.append(f"- Git ref: {handoff.git_ref}")
    sections.append(f"- CI pipeline: {handoff.ci_pipeline_url or 'N/A'}")

    if handoff.targets:
        sections.append("\n## Deployment Targets")
        for target in handoff.targets:
            sections.append(f"- **{target.environment}**: {target.url or 'N/A'}")
            if target.health_check_url:
                sections.append(f"  - Health check: {target.health_check_url}")
            sections.append(f"  - Replicas: {target.replicas}")
            if target.resource_limits:
                limits = ", ".join(f"{k}={v}" for k, v in target.resource_limits.items())
                sections.append(f"  - Resource limits: {limits}")

    if handoff.docker_images:
        sections.append("\n## Docker Images")
        for image in handoff.docker_images:
            sections.append(f"- {image}")

    if handoff.slo_targets:
        sections.append("\n## SLO Targets")
        for metric, slo_value in handoff.slo_targets.items():
            sections.append(f"- {metric}: {slo_value}")

    if handoff.rollback_command:
        sections.append(f"\n## Rollback Command\n```\n{handoff.rollback_command}\n```")

    gate_status = "PASSED" if handoff.quality_gate_passed else "FAILED"
    sections.append(f"\n## Deployment Quality Gate: {gate_status}")

    return "\n".join(sections)


# ── Quality evaluation ──────────────────────────────────────────────────


def _evaluate_quality(
    obs: ObservabilityResult,
    incident: IncidentResponseResult,
) -> bool:
    """Evaluate monitoring quality gate.

    Passes when all of:
    - At least one logging configuration generated
    - At least one Grafana dashboard generated
    - At least one alert rule file generated
    - At least one health endpoint generated
    """
    if not obs.logging_configs:
        return False
    if not obs.grafana_dashboards:
        return False
    if not incident.alert_rules:
        return False
    return bool(obs.health_endpoints)


# ── Result assembly ─────────────────────────────────────────────────────


def assemble_result(
    project_id: str,
    deployment_handoff: DeploymentToMonitoringHandoff,
    obs: ObservabilityResult,
    incident: IncidentResponseResult,
) -> MonitoringResult:
    """Assemble the MonitoringResult from agent outputs."""
    all_files: list[GeneratedFile] = [
        *obs.logging_configs,
        *obs.prometheus_configs,
        *obs.grafana_dashboards,
        *obs.health_endpoints,
        *incident.alert_rules,
        *incident.runbooks,
        *incident.incident_procedures,
    ]

    gate_passed = _evaluate_quality(obs, incident)

    notes_parts: list[str] = []
    if obs.notes:
        notes_parts.append(f"Observability: {obs.notes}")
    if incident.notes:
        notes_parts.append(f"Incident Response: {incident.notes}")

    return MonitoringResult(
        deployment_id=deployment_handoff.deployment_id,
        generated_files=all_files,
        slo_definitions=list(obs.slo_definitions),
        alert_rules=list(incident.alert_rule_definitions),
        quality_gate_passed=gate_passed,
        notes="; ".join(notes_parts),
    )


# ── Main supervisor ─────────────────────────────────────────────────────


async def supervise_monitoring(
    project_id: str,
    deployment_handoff: DeploymentToMonitoringHandoff,
    *,
    settings: Settings,
) -> MonitoringResult:
    """Orchestrate the Monitoring stage (FR-MON-*).

    Runs observability agent and incident response agent in parallel.
    Both are MUST requirements, so failure in either propagates.
    """
    logger.info("monitoring_supervisor.start", project_id=project_id)

    deploy_context = _deployment_to_context(deployment_handoff)

    obs, incident = await asyncio.gather(
        run_observability_agent(deploy_context, settings=settings),
        run_incident_response(deploy_context, settings=settings),
    )

    result = assemble_result(project_id, deployment_handoff, obs, incident)

    logger.info(
        "monitoring_supervisor.complete",
        project_id=project_id,
        deployment_id=result.deployment_id,
        files=len(result.generated_files),
        slos=len(result.slo_definitions),
        alerts=len(result.alert_rules),
        gate_passed=result.quality_gate_passed,
    )
    return result

"""Monitoring stage — observability, alerts, incident response (FR-MON-*, FR-ORC-001)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from colette.config import Settings
from colette.schemas.common import StageName, StageStatus
from colette.schemas.deployment import DeploymentToMonitoringHandoff
from colette.stages.monitoring.supervisor import supervise_monitoring

logger = structlog.get_logger(__name__)


async def run_stage(state: dict[str, Any]) -> dict[str, Any]:
    """Execute the Monitoring stage.

    Reads the Deployment handoff and produces monitoring configurations.
    As the terminal stage, there is no outgoing handoff schema — the result
    is stored under the monitoring key and ``completed_at`` is set.
    """
    project_id: str = state["project_id"]
    logger.info("stage.start", stage="monitoring", project_id=project_id)

    deployment_handoff_data = state.get("handoffs", {}).get(StageName.DEPLOYMENT.value)
    if not deployment_handoff_data:
        msg = "Monitoring stage requires a completed Deployment handoff in state"
        raise ValueError(msg)
    deployment_handoff = DeploymentToMonitoringHandoff.model_validate(
        deployment_handoff_data,
    )

    settings = Settings()
    result = await supervise_monitoring(
        project_id=project_id,
        deployment_handoff=deployment_handoff,
        settings=settings,
    )

    now = datetime.now(UTC).isoformat()

    logger.info(
        "stage.complete",
        stage="monitoring",
        project_id=project_id,
        deployment_id=result.deployment_id,
        gate_passed=result.quality_gate_passed,
    )

    return {
        "current_stage": StageName.MONITORING.value,
        "stage_statuses": {
            **state.get("stage_statuses", {}),
            StageName.MONITORING.value: StageStatus.COMPLETED.value,
        },
        "handoffs": {
            **state.get("handoffs", {}),
            StageName.MONITORING.value: result.to_dict(),
        },
        "completed_at": now,
        "progress_events": [
            {
                "stage": StageName.MONITORING.value,
                "status": StageStatus.COMPLETED.value,
                "timestamp": now,
            },
        ],
    }

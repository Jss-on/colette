"""Deployment stage stub — produces a dummy deployment handoff (FR-ORC-001)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from colette.schemas.common import DeploymentTarget, StageName, StageStatus
from colette.schemas.deployment import DeploymentToMonitoringHandoff

logger = structlog.get_logger()


async def run_stage(state: dict[str, Any]) -> dict[str, Any]:
    """Execute the deployment stage (stub)."""
    project_id = state["project_id"]
    logger.info("stage.start", stage="deployment", project_id=project_id)

    handoff = DeploymentToMonitoringHandoff(
        project_id=project_id,
        deployment_id=f"deploy-{project_id}-stub",
        targets=[
            DeploymentTarget(
                environment="staging",
                url="https://staging.example.com",
                health_check_url="https://staging.example.com/health",
            ),
        ],
        docker_images=["app:latest"],
        git_ref="main",
        rollback_command="kubectl rollout undo deployment/app",
        slo_targets={"availability": "99.9%", "p99_latency": "500ms"},
        quality_gate_passed=True,
    )

    logger.info("stage.complete", stage="deployment", project_id=project_id)
    return {
        "current_stage": StageName.DEPLOYMENT.value,
        "stage_statuses": {
            **state.get("stage_statuses", {}),
            StageName.DEPLOYMENT.value: StageStatus.COMPLETED.value,
        },
        "handoffs": {
            **state.get("handoffs", {}),
            StageName.DEPLOYMENT.value: handoff.to_dict(),
        },
        "progress_events": [
            {
                "stage": StageName.DEPLOYMENT.value,
                "status": StageStatus.COMPLETED.value,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        ],
    }

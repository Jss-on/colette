"""Deployment stage — tested code to staging/production (FR-DEP-*, FR-ORC-001)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from colette.config import Settings
from colette.schemas.common import StageName, StageStatus
from colette.schemas.testing import TestingToDeploymentHandoff
from colette.stages.deployment.supervisor import supervise_deployment

logger = structlog.get_logger(__name__)


async def run_stage(state: dict[str, Any]) -> dict[str, Any]:
    """Execute the Deployment stage.

    Reads the Testing handoff and produces deployment artifacts as a
    ``DeploymentToMonitoringHandoff``.
    """
    project_id: str = state["project_id"]

    structlog.contextvars.bind_contextvars(stage="deployment", project_id=project_id)
    try:
        logger.info("stage.start")

        # Retrieve testing handoff from previous stage
        testing_handoff_data = state.get("handoffs", {}).get(StageName.TESTING.value)
        if not testing_handoff_data:
            msg = "Deployment stage requires a completed Testing handoff in state"
            raise ValueError(msg)
        testing_handoff = TestingToDeploymentHandoff.model_validate(testing_handoff_data)

        settings = Settings()
        handoff, deploy_files = await supervise_deployment(
            project_id=project_id,
            testing_handoff=testing_handoff,
            settings=settings,
        )

        logger.info("stage.complete", deployment_id=handoff.deployment_id)
    finally:
        structlog.contextvars.unbind_contextvars("stage", "project_id")

    existing_gen = state.get("metadata", {}).get("generated_files", {})
    generated_files_serialized = [f.model_dump(mode="json") for f in deploy_files]

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
        "metadata": {
            **state.get("metadata", {}),
            "generated_files": {
                **existing_gen,
                StageName.DEPLOYMENT.value: generated_files_serialized,
            },
        },
        "progress_events": [
            {
                "stage": StageName.DEPLOYMENT.value,
                "status": StageStatus.COMPLETED.value,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        ],
    }

"""Testing stage — code to test reports (FR-TST-*, FR-ORC-001)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from colette.config import Settings
from colette.schemas.common import StageName, StageStatus
from colette.schemas.implementation import ImplementationToTestingHandoff
from colette.stages.testing.supervisor import supervise_testing

logger = structlog.get_logger(__name__)


async def run_stage(state: dict[str, Any]) -> dict[str, Any]:
    """Execute the Testing stage.

    Reads the Implementation handoff and produces test results as a
    ``TestingToDeploymentHandoff``.
    """
    project_id: str = state["project_id"]

    structlog.contextvars.bind_contextvars(stage="testing", project_id=project_id)
    try:
        logger.info("stage.start")

        # Retrieve implementation handoff from previous stage
        impl_handoff_data = state.get("handoffs", {}).get(StageName.IMPLEMENTATION.value)
        if not impl_handoff_data:
            msg = "Testing stage requires a completed Implementation handoff in state"
            raise ValueError(msg)
        impl_handoff = ImplementationToTestingHandoff.model_validate(impl_handoff_data)

        settings = Settings()
        handoff, test_files = await supervise_testing(
            project_id=project_id,
            impl_handoff=impl_handoff,
            settings=settings,
        )

        logger.info("stage.complete", readiness_score=handoff.deploy_readiness_score)
    finally:
        structlog.contextvars.unbind_contextvars("stage", "project_id")

    existing_gen = state.get("metadata", {}).get("generated_files", {})
    generated_files_serialized = [f.model_dump(mode="json") for f in test_files]

    return {
        "current_stage": StageName.TESTING.value,
        "stage_statuses": {
            **state.get("stage_statuses", {}),
            StageName.TESTING.value: StageStatus.COMPLETED.value,
        },
        "handoffs": {
            **state.get("handoffs", {}),
            StageName.TESTING.value: handoff.to_dict(),
        },
        "metadata": {
            **state.get("metadata", {}),
            "generated_files": {
                **existing_gen,
                StageName.TESTING.value: generated_files_serialized,
            },
        },
        "progress_events": [
            {
                "stage": StageName.TESTING.value,
                "status": StageStatus.COMPLETED.value,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        ],
    }

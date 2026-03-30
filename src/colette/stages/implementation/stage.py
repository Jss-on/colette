"""Implementation stage — design artifacts to code (FR-IMP-*, FR-ORC-001)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from colette.config import Settings
from colette.schemas.common import StageName, StageStatus
from colette.schemas.design import DesignToImplementationHandoff
from colette.stages.implementation.supervisor import supervise_implementation

logger = structlog.get_logger(__name__)


async def run_stage(state: dict[str, Any]) -> dict[str, Any]:
    """Execute the Implementation stage.

    Reads the Design handoff and produces generated code as an
    ``ImplementationToTestingHandoff``.
    """
    project_id: str = state["project_id"]
    logger.info("stage.start", stage="implementation", project_id=project_id)

    # Retrieve design handoff from previous stage
    design_handoff_data = state.get("handoffs", {}).get(StageName.DESIGN.value)
    if not design_handoff_data:
        msg = "Implementation stage requires a completed Design handoff in state"
        raise ValueError(msg)
    design_handoff = DesignToImplementationHandoff.model_validate(design_handoff_data)

    settings = Settings()
    handoff = await supervise_implementation(
        project_id=project_id,
        design_handoff=design_handoff,
        settings=settings,
    )

    logger.info(
        "stage.complete",
        stage="implementation",
        project_id=project_id,
        files=len(handoff.files_changed),
    )

    return {
        "current_stage": StageName.IMPLEMENTATION.value,
        "stage_statuses": {
            **state.get("stage_statuses", {}),
            StageName.IMPLEMENTATION.value: StageStatus.COMPLETED.value,
        },
        "handoffs": {
            **state.get("handoffs", {}),
            StageName.IMPLEMENTATION.value: handoff.to_dict(),
        },
        "progress_events": [
            {
                "stage": StageName.IMPLEMENTATION.value,
                "status": StageStatus.COMPLETED.value,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        ],
    }

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

    structlog.contextvars.bind_contextvars(stage="implementation", project_id=project_id)
    try:
        logger.info("stage.start")

        # Retrieve design handoff from previous stage
        design_handoff_data = state.get("handoffs", {}).get(StageName.DESIGN.value)
        if not design_handoff_data:
            msg = "Implementation stage requires a completed Design handoff in state"
            raise ValueError(msg)
        design_handoff = DesignToImplementationHandoff.model_validate(design_handoff_data)

        settings = Settings()
        result = await supervise_implementation(
            project_id=project_id,
            design_handoff=design_handoff,
            settings=settings,
        )

        logger.info("stage.complete", files=len(result.handoff.files_changed))
    finally:
        structlog.contextvars.unbind_contextvars("stage", "project_id")

    # Persist generated file contents in metadata so gate reviews can
    # show actual source code to the user.
    existing_gen = state.get("metadata", {}).get("generated_files", {})
    generated_files_serialized = [f.model_dump(mode="json") for f in result.generated_files]

    return {
        "current_stage": StageName.IMPLEMENTATION.value,
        "stage_statuses": {
            **state.get("stage_statuses", {}),
            StageName.IMPLEMENTATION.value: StageStatus.COMPLETED.value,
        },
        "handoffs": {
            **state.get("handoffs", {}),
            StageName.IMPLEMENTATION.value: result.handoff.to_dict(),
        },
        "metadata": {
            **state.get("metadata", {}),
            "generated_files": {
                **existing_gen,
                StageName.IMPLEMENTATION.value: generated_files_serialized,
            },
        },
        "progress_events": [
            {
                "stage": StageName.IMPLEMENTATION.value,
                "status": StageStatus.COMPLETED.value,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        ],
    }

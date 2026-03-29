"""Implementation stage stub — produces a dummy code handoff (FR-ORC-001)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from colette.schemas.common import FileDiff, StageName, StageStatus
from colette.schemas.implementation import ImplementationToTestingHandoff

logger = structlog.get_logger()


async def run_stage(state: dict[str, Any]) -> dict[str, Any]:
    """Execute the implementation stage (stub)."""
    project_id = state["project_id"]
    logger.info("stage.start", stage="implementation", project_id=project_id)

    handoff = ImplementationToTestingHandoff(
        project_id=project_id,
        git_repo_url="https://github.com/stub/repo",
        git_ref="main",
        commit_shas=["abc1234"],
        files_changed=[
            FileDiff(path="src/app.py", action="added", language="python", lines_added=50),
        ],
        lint_passed=True,
        type_check_passed=True,
        build_passed=True,
        quality_gate_passed=True,
    )

    logger.info("stage.complete", stage="implementation", project_id=project_id)
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

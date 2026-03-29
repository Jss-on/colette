"""Testing stage stub — produces a dummy test report handoff (FR-ORC-001)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from colette.schemas.common import StageName, StageStatus, SuiteResult
from colette.schemas.testing import TestingToDeploymentHandoff

logger = structlog.get_logger()


async def run_stage(state: dict[str, Any]) -> dict[str, Any]:
    """Execute the testing stage (stub)."""
    project_id = state["project_id"]
    logger.info("stage.start", stage="testing", project_id=project_id)

    handoff = TestingToDeploymentHandoff(
        project_id=project_id,
        test_results=[
            SuiteResult(category="unit", total=42, passed=42, line_coverage=85.0),
            SuiteResult(category="integration", total=10, passed=10),
        ],
        overall_line_coverage=85.0,
        overall_branch_coverage=75.0,
        contract_tests_passed=True,
        deploy_readiness_score=90,
        git_ref="main",
        quality_gate_passed=True,
    )

    logger.info("stage.complete", stage="testing", project_id=project_id)
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
        "progress_events": [
            {
                "stage": StageName.TESTING.value,
                "status": StageStatus.COMPLETED.value,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        ],
    }

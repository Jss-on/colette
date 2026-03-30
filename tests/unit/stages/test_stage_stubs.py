"""Tests for stage stubs (implementation, testing, deployment, monitoring).

Requirements and Design stages are now real implementations and have
their own test files: test_requirements_stage.py and test_design_stage.py.
"""

from __future__ import annotations

import pytest

from colette.orchestrator.state import create_initial_state
from colette.schemas.common import StageName, StageStatus
from colette.stages.deployment.stage import run_stage as deployment_run
from colette.stages.implementation.stage import run_stage as implementation_run
from colette.stages.monitoring.stage import run_stage as monitoring_run
from colette.stages.testing.stage import run_stage as run_testing_stage


@pytest.fixture
def initial_state() -> dict:
    return dict(create_initial_state("test-project"))


class TestImplementationStub:
    @pytest.mark.asyncio
    async def test_produces_valid_handoff(self, initial_state: dict) -> None:
        result = await implementation_run(initial_state)
        handoff = result["handoffs"][StageName.IMPLEMENTATION.value]
        assert handoff["lint_passed"] is True
        assert handoff["build_passed"] is True


class TestTestingStub:
    @pytest.mark.asyncio
    async def test_produces_valid_handoff(self, initial_state: dict) -> None:
        result = await run_testing_stage(initial_state)
        handoff = result["handoffs"][StageName.TESTING.value]
        assert handoff["overall_line_coverage"] == 85.0
        assert handoff["contract_tests_passed"] is True


class TestDeploymentStub:
    @pytest.mark.asyncio
    async def test_produces_valid_handoff(self, initial_state: dict) -> None:
        result = await deployment_run(initial_state)
        handoff = result["handoffs"][StageName.DEPLOYMENT.value]
        assert len(handoff["targets"]) > 0
        assert handoff["rollback_command"] != ""


class TestMonitoringStub:
    @pytest.mark.asyncio
    async def test_sets_completed_at(self, initial_state: dict) -> None:
        result = await monitoring_run(initial_state)
        assert result["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_marks_stage_completed(self, initial_state: dict) -> None:
        result = await monitoring_run(initial_state)
        assert result["stage_statuses"][StageName.MONITORING.value] == StageStatus.COMPLETED.value

"""Tests for all 6 stage stubs."""

from __future__ import annotations

import pytest

from colette.orchestrator.state import create_initial_state
from colette.schemas.common import StageName, StageStatus
from colette.stages.deployment.stage import run_stage as deployment_run
from colette.stages.design.stage import run_stage as design_run
from colette.stages.implementation.stage import run_stage as implementation_run
from colette.stages.monitoring.stage import run_stage as monitoring_run
from colette.stages.requirements.stage import run_stage as requirements_run
from colette.stages.testing.stage import run_stage as run_testing_stage


@pytest.fixture
def initial_state() -> dict:
    return dict(create_initial_state("test-project"))


class TestRequirementsStub:
    @pytest.mark.asyncio
    async def test_produces_valid_handoff(self, initial_state: dict) -> None:
        result = await requirements_run(initial_state)
        assert StageName.REQUIREMENTS.value in result["handoffs"]
        handoff = result["handoffs"][StageName.REQUIREMENTS.value]
        assert handoff["source_stage"] == "requirements"
        assert handoff["target_stage"] == "design"

    @pytest.mark.asyncio
    async def test_marks_stage_completed(self, initial_state: dict) -> None:
        result = await requirements_run(initial_state)
        assert result["stage_statuses"][StageName.REQUIREMENTS.value] == StageStatus.COMPLETED.value

    @pytest.mark.asyncio
    async def test_emits_progress_event(self, initial_state: dict) -> None:
        result = await requirements_run(initial_state)
        assert len(result["progress_events"]) == 1
        assert result["progress_events"][0]["stage"] == "requirements"


class TestDesignStub:
    @pytest.mark.asyncio
    async def test_produces_valid_handoff(self, initial_state: dict) -> None:
        result = await design_run(initial_state)
        handoff = result["handoffs"][StageName.DESIGN.value]
        assert handoff["source_stage"] == "design"
        assert "openapi_spec" in handoff


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

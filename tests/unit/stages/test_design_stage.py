"""Tests for the Design stage (Phase 4)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from colette.schemas.common import (
    ADRRecord,
    ComponentSpec,
    EndpointSpec,
    EntitySpec,
    StageName,
    UserStory,
)
from colette.schemas.requirements import RequirementsToDesignHandoff
from colette.stages.design.api_designer import APIDesignResult
from colette.stages.design.architect import ArchitectureResult
from colette.stages.design.stage import run_stage
from colette.stages.design.supervisor import (
    _generate_tasks,
    _prd_to_text,
    assemble_handoff,
    supervise_design,
)
from colette.stages.design.ui_designer import UIDesignResult

# ── Fixtures ────────────────────────────────────────────────────────────


def _make_prd_handoff() -> RequirementsToDesignHandoff:
    return RequirementsToDesignHandoff(
        project_id="proj-1",
        project_overview="A simple todo application.",
        functional_requirements=[
            UserStory(
                id="US-REQ-001",
                title="Create todo",
                persona="user",
                goal="create a new todo item",
                benefit="track my tasks",
                acceptance_criteria=["Todo is saved", "Todo appears in list"],
            ),
            UserStory(
                id="US-REQ-002",
                title="List todos",
                persona="user",
                goal="see all my todos",
                benefit="overview of tasks",
                acceptance_criteria=["All todos visible"],
            ),
        ],
        completeness_score=0.90,
        quality_gate_passed=True,
    )


def _make_arch_result() -> ArchitectureResult:
    return ArchitectureResult(
        architecture_summary="Monolith with React frontend and FastAPI backend.",
        tech_stack={
            "frontend": "React/Next.js",
            "backend": "Python/FastAPI",
            "database": "PostgreSQL",
        },
        db_entities=[
            EntitySpec(
                name="todos",
                fields=[
                    {"name": "id", "type": "uuid", "constraints": "PRIMARY KEY"},
                    {"name": "title", "type": "varchar(255)", "constraints": "NOT NULL"},
                    {"name": "completed", "type": "boolean", "constraints": "DEFAULT false"},
                ],
                indexes=["idx_todos_completed"],
            ),
            EntitySpec(
                name="users",
                fields=[
                    {"name": "id", "type": "uuid", "constraints": "PRIMARY KEY"},
                    {"name": "email", "type": "varchar(255)", "constraints": "UNIQUE NOT NULL"},
                ],
            ),
        ],
        adrs=[
            ADRRecord(
                id="ADR-001",
                title="Use PostgreSQL for persistence",
                status="accepted",
                context="Need a relational database.",
                decision="PostgreSQL for reliability.",
                alternatives=["SQLite", "MongoDB"],
                consequences=["Requires PostgreSQL in deployment"],
            ),
        ],
        security_design="JWT-based authentication with bcrypt password hashing.",
        migration_strategy="Alembic for schema migrations.",
    )


def _make_api_result() -> APIDesignResult:
    spec = json.dumps({
        "openapi": "3.1.0",
        "info": {"title": "Todo API", "version": "1.0.0"},
        "paths": {
            "/api/v1/todos": {
                "get": {"summary": "List todos"},
                "post": {"summary": "Create todo"},
            },
            "/api/v1/todos/{id}": {
                "get": {"summary": "Get todo"},
                "put": {"summary": "Update todo"},
                "delete": {"summary": "Delete todo"},
            },
        },
    })
    return APIDesignResult(
        openapi_spec=spec,
        endpoints=[
            EndpointSpec(method="GET", path="/api/v1/todos", summary="List todos"),
            EndpointSpec(method="POST", path="/api/v1/todos", summary="Create todo"),
            EndpointSpec(method="GET", path="/api/v1/todos/{id}", summary="Get todo"),
        ],
    )


def _make_ui_result() -> UIDesignResult:
    return UIDesignResult(
        ui_components=[
            ComponentSpec(
                name="TodoList",
                description="Displays list of todos",
                route="/todos",
            ),
            ComponentSpec(
                name="TodoForm",
                description="Form for creating a new todo",
            ),
        ],
        navigation_flows=["Login -> Dashboard -> Todo List -> Todo Detail"],
    )


# ── _prd_to_text ────────────────────────────────────────────────────────


class TestPrdToText:
    def test_includes_overview(self) -> None:
        prd = _make_prd_handoff()
        text = _prd_to_text(prd)
        assert "todo application" in text.lower()

    def test_includes_story_ids(self) -> None:
        prd = _make_prd_handoff()
        text = _prd_to_text(prd)
        assert "US-REQ-001" in text
        assert "US-REQ-002" in text

    def test_includes_acceptance_criteria(self) -> None:
        prd = _make_prd_handoff()
        text = _prd_to_text(prd)
        assert "Todo is saved" in text


# ── _generate_tasks ─────────────────────────────────────────────────────


class TestGenerateTasks:
    def test_creates_scaffolding_task(self) -> None:
        tasks = _generate_tasks(_make_arch_result(), _make_api_result(), _make_ui_result())
        assert tasks[0].description == "Set up project scaffolding and build system"
        assert tasks[0].id == "TASK-001"

    def test_creates_db_migration_tasks(self) -> None:
        arch = _make_arch_result()
        tasks = _generate_tasks(arch, _make_api_result(), _make_ui_result())
        db_tasks = [t for t in tasks if "migration" in t.description.lower()]
        assert len(db_tasks) == len(arch.db_entities)

    def test_creates_endpoint_tasks(self) -> None:
        api = _make_api_result()
        tasks = _generate_tasks(_make_arch_result(), api, _make_ui_result())
        ep_tasks = [t for t in tasks if "Implement" in t.description and "/" in t.description]
        assert len(ep_tasks) == len(api.endpoints)

    def test_creates_component_tasks(self) -> None:
        ui = _make_ui_result()
        tasks = _generate_tasks(_make_arch_result(), _make_api_result(), ui)
        comp_tasks = [t for t in tasks if "component" in t.description.lower()]
        assert len(comp_tasks) == len(ui.ui_components)

    def test_tasks_have_unique_ids(self) -> None:
        tasks = _generate_tasks(_make_arch_result(), _make_api_result(), _make_ui_result())
        ids = [t.id for t in tasks]
        assert len(ids) == len(set(ids))

    def test_db_tasks_depend_on_scaffolding(self) -> None:
        tasks = _generate_tasks(_make_arch_result(), _make_api_result(), _make_ui_result())
        db_tasks = [t for t in tasks if "migration" in t.description.lower()]
        for task in db_tasks:
            assert "TASK-001" in task.dependencies


# ── assemble_handoff ────────────────────────────────────────────────────


class TestAssembleHandoff:
    def test_basic_assembly(self) -> None:
        handoff = assemble_handoff(
            "proj-1", _make_arch_result(), _make_api_result(), _make_ui_result(),
        )
        assert handoff.project_id == "proj-1"
        assert handoff.source_stage == "design"
        assert handoff.target_stage == "implementation"
        assert handoff.architecture_summary != ""
        assert handoff.openapi_spec != ""
        assert len(handoff.db_entities) == 2
        assert len(handoff.endpoints) == 3
        assert len(handoff.ui_components) == 2
        assert len(handoff.adrs) == 1
        assert len(handoff.tasks) > 0
        assert handoff.quality_gate_passed is True


# ── supervise_design ────────────────────────────────────────────────────


class TestSuperviseDesign:
    @pytest.mark.asyncio
    async def test_produces_handoff(self, settings: object) -> None:
        prd = _make_prd_handoff()

        with (
            patch(
                "colette.stages.design.supervisor.run_architect",
                new_callable=AsyncMock,
                return_value=_make_arch_result(),
            ),
            patch(
                "colette.stages.design.supervisor.run_api_designer",
                new_callable=AsyncMock,
                return_value=_make_api_result(),
            ),
            patch(
                "colette.stages.design.supervisor.run_ui_designer",
                new_callable=AsyncMock,
                return_value=_make_ui_result(),
            ),
        ):
            handoff = await supervise_design(
                "proj-1", prd, settings=settings,  # type: ignore[arg-type]
            )

        assert handoff.project_id == "proj-1"
        assert len(handoff.endpoints) == 3
        assert len(handoff.db_entities) == 2
        assert len(handoff.ui_components) == 2


# ── run_stage ───────────────────────────────────────────────────────────


class TestRunStage:
    @pytest.mark.asyncio
    async def test_produces_valid_state_update(self) -> None:
        prd = _make_prd_handoff()

        state = {
            "project_id": "test-proj",
            "stage_statuses": {},
            "handoffs": {
                StageName.REQUIREMENTS.value: prd.to_dict(),
            },
        }

        with (
            patch(
                "colette.stages.design.supervisor.run_architect",
                new_callable=AsyncMock,
                return_value=_make_arch_result(),
            ),
            patch(
                "colette.stages.design.supervisor.run_api_designer",
                new_callable=AsyncMock,
                return_value=_make_api_result(),
            ),
            patch(
                "colette.stages.design.supervisor.run_ui_designer",
                new_callable=AsyncMock,
                return_value=_make_ui_result(),
            ),
            patch("colette.stages.design.stage.Settings"),
        ):
            result = await run_stage(state)

        assert result["current_stage"] == "design"
        assert result["stage_statuses"]["design"] == "completed"
        assert "design" in result["handoffs"]
        handoff = result["handoffs"]["design"]
        assert handoff["source_stage"] == "design"
        assert "openapi_spec" in handoff
        assert len(result["progress_events"]) == 1

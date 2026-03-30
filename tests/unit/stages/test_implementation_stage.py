"""Tests for the Implementation stage (Phase 5)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from colette.schemas.common import (
    ADRRecord,
    ComponentSpec,
    EndpointSpec,
    EntitySpec,
    GeneratedFile,
    Severity,
    StageName,
)
from colette.schemas.design import DesignToImplementationHandoff, ImplementationTask
from colette.stages.implementation.backend import BackendResult
from colette.stages.implementation.database import DatabaseResult
from colette.stages.implementation.frontend import FrontendResult
from colette.stages.implementation.stage import run_stage
from colette.stages.implementation.supervisor import (
    CrossReviewResult,
    ReviewFinding,
    _collect_env_vars,
    _collect_files,
    _design_to_context,
    _evaluate_quality,
    _parse_endpoints,
    assemble_handoff,
    supervise_implementation,
)

# ── Fixtures ────────────────────────────────────────────────────────────


def _make_design_handoff() -> DesignToImplementationHandoff:
    spec = json.dumps(
        {
            "openapi": "3.1.0",
            "info": {"title": "Todo API", "version": "1.0.0"},
            "paths": {
                "/api/v1/todos": {
                    "get": {"summary": "List todos"},
                    "post": {"summary": "Create todo"},
                },
            },
        }
    )
    return DesignToImplementationHandoff(
        project_id="proj-1",
        architecture_summary="Monolith with React frontend and FastAPI backend.",
        tech_stack={
            "frontend": "React/Next.js",
            "backend": "Python/FastAPI",
            "database": "PostgreSQL",
        },
        openapi_spec=spec,
        endpoints=[
            EndpointSpec(method="GET", path="/api/v1/todos", summary="List todos"),
            EndpointSpec(method="POST", path="/api/v1/todos", summary="Create todo"),
        ],
        db_entities=[
            EntitySpec(
                name="todos",
                fields=[
                    {"name": "id", "type": "uuid", "constraints": "PRIMARY KEY"},
                    {"name": "title", "type": "varchar(255)", "constraints": "NOT NULL"},
                ],
                indexes=["idx_todos_completed"],
            ),
        ],
        migration_strategy="Alembic for schema migrations.",
        ui_components=[
            ComponentSpec(name="TodoList", description="Displays todos", route="/todos"),
        ],
        navigation_flows=["Login -> Dashboard -> Todo List"],
        adrs=[
            ADRRecord(id="ADR-001", title="Use PostgreSQL", status="accepted"),
        ],
        security_design="JWT-based authentication.",
        tasks=[
            ImplementationTask(id="TASK-001", description="Set up scaffolding"),
            ImplementationTask(
                id="TASK-002",
                description="Create todos migration",
                dependencies=["TASK-001"],
                assigned_agent="db_engineer",
            ),
        ],
        quality_gate_passed=True,
    )


def _make_frontend_result() -> FrontendResult:
    return FrontendResult(
        files=[
            GeneratedFile(
                path="src/components/TodoList.tsx",
                content="export function TodoList() { return <div>Todos</div>; }",
                language="typescript",
            ),
            GeneratedFile(
                path="src/pages/index.tsx",
                content="export default function Home() { return <TodoList />; }",
                language="typescript",
            ),
        ],
        packages=["react-hook-form", "zustand"],
        env_vars=["NEXT_PUBLIC_API_URL"],
        notes="Uses Tailwind CSS for styling.",
    )


def _make_backend_result() -> BackendResult:
    return BackendResult(
        files=[
            GeneratedFile(
                path="src/routes/todos.py",
                content='@router.get("/api/v1/todos")\nasync def list_todos(): ...',
                language="python",
            ),
            GeneratedFile(
                path="src/auth/jwt.py",
                content="def verify_token(token: str): ...",
                language="python",
            ),
        ],
        packages=["fastapi", "pyjwt", "bcrypt"],
        env_vars=["DATABASE_URL", "JWT_SECRET"],
        implemented_endpoints=["GET /api/v1/todos", "POST /api/v1/todos"],
        auth_strategy="JWT with bcrypt",
    )


def _make_database_result() -> DatabaseResult:
    return DatabaseResult(
        files=[
            GeneratedFile(
                path="models/todo.py",
                content="class Todo(Base): ...",
                language="python",
            ),
            GeneratedFile(
                path="migrations/001_initial.py",
                content="def upgrade(): ...\ndef downgrade(): ...",
                language="python",
            ),
        ],
        packages=["sqlalchemy", "alembic"],
        entities_created=["todos"],
        migrations=["migrations/001_initial.py"],
        seed_data_included=True,
    )


def _make_review_result() -> CrossReviewResult:
    return CrossReviewResult(
        findings=[
            ReviewFinding(
                severity=Severity.MEDIUM,
                category="type inconsistency",
                description="Frontend expects 'completed' as boolean, "
                "backend returns 'is_completed'.",
                location="src/components/TodoList.tsx",
            ),
        ],
        summary="Minor naming inconsistency found.",
    )


# ── _design_to_context ──────────────────────────────────────────────────


class TestDesignToContext:
    def test_includes_architecture(self) -> None:
        ctx = _design_to_context(_make_design_handoff())
        assert "Monolith" in ctx

    def test_includes_tech_stack(self) -> None:
        ctx = _design_to_context(_make_design_handoff())
        assert "React/Next.js" in ctx
        assert "FastAPI" in ctx

    def test_includes_endpoints(self) -> None:
        ctx = _design_to_context(_make_design_handoff())
        assert "GET /api/v1/todos" in ctx
        assert "POST /api/v1/todos" in ctx

    def test_includes_db_entities(self) -> None:
        ctx = _design_to_context(_make_design_handoff())
        assert "todos" in ctx

    def test_includes_ui_components(self) -> None:
        ctx = _design_to_context(_make_design_handoff())
        assert "TodoList" in ctx

    def test_includes_security_design(self) -> None:
        ctx = _design_to_context(_make_design_handoff())
        assert "JWT" in ctx

    def test_includes_tasks(self) -> None:
        ctx = _design_to_context(_make_design_handoff())
        assert "TASK-001" in ctx
        assert "TASK-002" in ctx


# ── _collect_files ──────────────────────────────────────────────────────


class TestCollectFiles:
    def test_collects_all_files(self) -> None:
        files = _collect_files(
            _make_frontend_result(),
            _make_backend_result(),
            _make_database_result(),
        )
        assert len(files) == 6  # 2 + 2 + 2

    def test_all_files_are_added(self) -> None:
        files = _collect_files(
            _make_frontend_result(),
            _make_backend_result(),
            _make_database_result(),
        )
        assert all(f.action == "added" for f in files)

    def test_lines_added_positive(self) -> None:
        files = _collect_files(
            _make_frontend_result(),
            _make_backend_result(),
            _make_database_result(),
        )
        assert all(f.lines_added > 0 for f in files)


# ── _collect_env_vars ───────────────────────────────────────────────────


class TestCollectEnvVars:
    def test_merges_and_dedupes(self) -> None:
        frontend = _make_frontend_result()
        backend = _make_backend_result()
        env_vars = _collect_env_vars(frontend, backend)
        assert "NEXT_PUBLIC_API_URL" in env_vars
        assert "DATABASE_URL" in env_vars
        assert "JWT_SECRET" in env_vars
        assert len(env_vars) == len(set(env_vars))  # no dupes


# ── _parse_endpoints ────────────────────────────────────────────────────


class TestParseEndpoints:
    def test_matches_implemented_endpoints(self) -> None:
        backend = _make_backend_result()
        design = _make_design_handoff()
        endpoints = _parse_endpoints(backend, design)
        assert len(endpoints) == 2

    def test_unmatched_endpoints_excluded(self) -> None:
        backend = BackendResult(
            files=[],
            implemented_endpoints=["DELETE /api/v1/nonexistent"],
        )
        design = _make_design_handoff()
        endpoints = _parse_endpoints(backend, design)
        assert len(endpoints) == 0


# ── _evaluate_quality ───────────────────────────────────────────────────


class TestEvaluateQuality:
    def test_passes_with_files_and_no_critical(self) -> None:
        assert (
            _evaluate_quality(
                _make_frontend_result(),
                _make_backend_result(),
                _make_database_result(),
                _make_review_result(),
            )
            is True
        )

    def test_fails_with_empty_frontend(self) -> None:
        assert (
            _evaluate_quality(
                FrontendResult(files=[]),
                _make_backend_result(),
                _make_database_result(),
                None,
            )
            is False
        )

    def test_fails_with_empty_backend(self) -> None:
        assert (
            _evaluate_quality(
                _make_frontend_result(),
                BackendResult(files=[]),
                _make_database_result(),
                None,
            )
            is False
        )

    def test_fails_with_empty_database(self) -> None:
        assert (
            _evaluate_quality(
                _make_frontend_result(),
                _make_backend_result(),
                DatabaseResult(files=[]),
                None,
            )
            is False
        )

    def test_fails_with_critical_finding(self) -> None:
        review = CrossReviewResult(
            findings=[
                ReviewFinding(
                    severity=Severity.CRITICAL,
                    category="API contract mismatch",
                    description="Endpoint returns wrong schema.",
                ),
            ],
        )
        assert (
            _evaluate_quality(
                _make_frontend_result(),
                _make_backend_result(),
                _make_database_result(),
                review,
            )
            is False
        )

    def test_passes_with_no_review(self) -> None:
        assert (
            _evaluate_quality(
                _make_frontend_result(),
                _make_backend_result(),
                _make_database_result(),
                None,
            )
            is True
        )


# ── assemble_handoff ────────────────────────────────────────────────────


class TestAssembleHandoff:
    def test_basic_assembly(self) -> None:
        handoff = assemble_handoff(
            "proj-1",
            _make_design_handoff(),
            _make_frontend_result(),
            _make_backend_result(),
            _make_database_result(),
            _make_review_result(),
        )
        assert handoff.project_id == "proj-1"
        assert handoff.source_stage == "implementation"
        assert handoff.target_stage == "testing"
        assert len(handoff.files_changed) == 6
        assert len(handoff.env_vars) == 3
        assert handoff.quality_gate_passed is True

    def test_includes_test_hints_from_review(self) -> None:
        handoff = assemble_handoff(
            "proj-1",
            _make_design_handoff(),
            _make_frontend_result(),
            _make_backend_result(),
            _make_database_result(),
            _make_review_result(),
        )
        assert len(handoff.test_hints) == 1
        assert "type inconsistency" in handoff.test_hints[0]

    def test_assembly_without_review(self) -> None:
        handoff = assemble_handoff(
            "proj-1",
            _make_design_handoff(),
            _make_frontend_result(),
            _make_backend_result(),
            _make_database_result(),
            None,
        )
        assert handoff.quality_gate_passed is True
        assert handoff.test_hints == []


# ── supervise_implementation ────────────────────────────────────────────


class TestSuperviseImplementation:
    @pytest.mark.asyncio
    async def test_produces_handoff(self, settings: object) -> None:
        design = _make_design_handoff()

        with (
            patch(
                "colette.stages.implementation.supervisor.run_frontend",
                new_callable=AsyncMock,
                return_value=_make_frontend_result(),
            ),
            patch(
                "colette.stages.implementation.supervisor.run_backend",
                new_callable=AsyncMock,
                return_value=_make_backend_result(),
            ),
            patch(
                "colette.stages.implementation.supervisor.run_database",
                new_callable=AsyncMock,
                return_value=_make_database_result(),
            ),
            patch(
                "colette.stages.implementation.supervisor._run_cross_review",
                new_callable=AsyncMock,
                return_value=_make_review_result(),
            ),
        ):
            handoff = await supervise_implementation(
                "proj-1",
                design,
                settings=settings,  # type: ignore[arg-type]
            )

        assert handoff.project_id == "proj-1"
        assert len(handoff.files_changed) == 6
        assert handoff.quality_gate_passed is True

    @pytest.mark.asyncio
    async def test_handles_cross_review_failure(self, settings: object) -> None:
        design = _make_design_handoff()

        with (
            patch(
                "colette.stages.implementation.supervisor.run_frontend",
                new_callable=AsyncMock,
                return_value=_make_frontend_result(),
            ),
            patch(
                "colette.stages.implementation.supervisor.run_backend",
                new_callable=AsyncMock,
                return_value=_make_backend_result(),
            ),
            patch(
                "colette.stages.implementation.supervisor.run_database",
                new_callable=AsyncMock,
                return_value=_make_database_result(),
            ),
            patch(
                "colette.stages.implementation.supervisor._run_cross_review",
                new_callable=AsyncMock,
                side_effect=RuntimeError("LLM timeout"),
            ),
        ):
            handoff = await supervise_implementation(
                "proj-1",
                design,
                settings=settings,  # type: ignore[arg-type]
            )

        # Cross-review is SHOULD, so failure doesn't block
        assert handoff.quality_gate_passed is True
        assert handoff.test_hints == []


# ── run_stage ───────────────────────────────────────────────────────────


class TestRunStage:
    @pytest.mark.asyncio
    async def test_raises_on_missing_design_handoff(self) -> None:
        state = {
            "project_id": "test-proj",
            "stage_statuses": {},
            "handoffs": {},
        }
        with pytest.raises(ValueError, match="requires a completed Design handoff"):
            await run_stage(state)

    @pytest.mark.asyncio
    async def test_produces_valid_state_update(self) -> None:
        design = _make_design_handoff()

        state = {
            "project_id": "test-proj",
            "stage_statuses": {},
            "handoffs": {
                StageName.DESIGN.value: design.to_dict(),
            },
        }

        with (
            patch(
                "colette.stages.implementation.supervisor.run_frontend",
                new_callable=AsyncMock,
                return_value=_make_frontend_result(),
            ),
            patch(
                "colette.stages.implementation.supervisor.run_backend",
                new_callable=AsyncMock,
                return_value=_make_backend_result(),
            ),
            patch(
                "colette.stages.implementation.supervisor.run_database",
                new_callable=AsyncMock,
                return_value=_make_database_result(),
            ),
            patch(
                "colette.stages.implementation.supervisor._run_cross_review",
                new_callable=AsyncMock,
                return_value=_make_review_result(),
            ),
            patch("colette.stages.implementation.stage.Settings"),
        ):
            result = await run_stage(state)

        assert result["current_stage"] == "implementation"
        assert result["stage_statuses"]["implementation"] == "completed"
        assert "implementation" in result["handoffs"]
        handoff = result["handoffs"]["implementation"]
        assert handoff["source_stage"] == "implementation"
        assert len(handoff["files_changed"]) == 6
        assert len(result["progress_events"]) == 1

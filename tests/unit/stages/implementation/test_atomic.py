"""Tests for atomic code generation."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from colette.schemas.atomic import (
    AtomicBackendUnit,
    AtomicDatabaseUnit,
    AtomicFrontendUnit,
    AtomicGenerationProgress,
    AtomicScaffoldUnit,
    AtomicUnitKind,
    AtomicUnitResult,
    AtomicUnitSpec,
)
from colette.schemas.common import (
    ComponentSpec,
    EndpointSpec,
    EntitySpec,
    GeneratedFile,
)
from colette.schemas.design import DesignToImplementationHandoff
from colette.stages.implementation.atomic import (
    _classify_file_domain,
    _extract_signatures,
    _is_auth_endpoint,
    build_incremental_context,
    extract_atomic_units,
    run_atomic_generation,
    topological_sort_units,
    verify_and_fix_unit,
)
from colette.stages.implementation.supervisor import _progress_to_agent_results
from colette.stages.implementation.verifier import (
    VerificationFinding,
    VerificationReport,
    filter_findings_to_paths,
)

# ── Fixtures ──────────────────────────────────────────────────────────


def _file(
    path: str = "src/main.py",
    content: str = "# ok",
    lang: str = "python",
) -> GeneratedFile:
    return GeneratedFile(path=path, content=content, language=lang)


def _entity(name: str, rels: list[str] | None = None) -> EntitySpec:
    return EntitySpec(
        name=name,
        fields=[
            {"name": "id", "type": "int"},
            {"name": "name", "type": "str"},
        ],
        relationships=rels or [],
    )


def _endpoint(
    method: str,
    path: str,
    auth: bool = True,
    summary: str = "",
) -> EndpointSpec:
    return EndpointSpec(method=method, path=path, auth_required=auth, summary=summary)


def _component(
    name: str,
    children: list[str] | None = None,
    route: str | None = None,
) -> ComponentSpec:
    return ComponentSpec(
        name=name,
        description=f"{name} component",
        children=children or [],
        route=route,
    )


def _handoff(**kwargs: object) -> DesignToImplementationHandoff:
    defaults: dict[str, object] = {
        "project_id": "test-proj",
        "architecture_summary": "Simple REST API",
        "tech_stack": {"backend": "FastAPI", "frontend": "Next.js"},
        "openapi_spec": "{}",
        "db_entities": [],
        "endpoints": [],
        "ui_components": [],
    }
    defaults.update(kwargs)
    return DesignToImplementationHandoff(**defaults)


def _clean_report() -> VerificationReport:
    return VerificationReport(
        lint_passed=True,
        type_check_passed=True,
        build_passed=True,
    )


# ── extract_atomic_units ─────────────────────────────────────────────


class TestExtractAtomicUnits:
    def test_always_includes_scaffold(self) -> None:
        handoff = _handoff()
        units = extract_atomic_units(handoff, None)
        scaffold = [u for u in units if u.kind == AtomicUnitKind.SCAFFOLDING]
        assert len(scaffold) == 1
        assert scaffold[0].name == "project_scaffold"
        assert scaffold[0].phase == 0

    def test_extracts_database_entities(self) -> None:
        handoff = _handoff(
            db_entities=[
                _entity("User"),
                _entity("Post", rels=["belongs_to:User"]),
            ]
        )
        units = extract_atomic_units(handoff, None)
        db_units = [u for u in units if u.kind == AtomicUnitKind.DATABASE_ENTITY]
        assert len(db_units) == 2
        user_unit = next(u for u in db_units if u.name == "User")
        post_unit = next(u for u in db_units if u.name == "Post")
        assert user_unit.depends_on == ()
        assert "User" in post_unit.depends_on
        assert all(u.phase == 1 for u in db_units)

    def test_extracts_endpoints_with_auth_ordering(self) -> None:
        handoff = _handoff(
            endpoints=[
                _endpoint("POST", "/api/auth/login", summary="Login"),
                _endpoint("GET", "/api/todos"),
            ]
        )
        units = extract_atomic_units(handoff, None)
        ep_units = [u for u in units if u.kind == AtomicUnitKind.BACKEND_ENDPOINT]
        assert len(ep_units) == 2
        login = next(u for u in ep_units if "login" in u.name.lower())
        todos = next(u for u in ep_units if "todos" in u.name.lower())
        assert login.depends_on == ()
        assert login.name in todos.depends_on

    def test_extracts_frontend_components_leaf_first(self) -> None:
        handoff = _handoff(
            ui_components=[
                _component("Button"),
                _component("TodoList", children=["Button"]),
                _component("HomePage", children=["TodoList"], route="/"),
            ]
        )
        units = extract_atomic_units(handoff, None)
        comp_units = [u for u in units if u.kind == AtomicUnitKind.FRONTEND_COMPONENT]
        assert len(comp_units) == 3
        home = next(u for u in comp_units if u.name == "HomePage")
        todo_list = next(u for u in comp_units if u.name == "TodoList")
        button = next(u for u in comp_units if u.name == "Button")
        assert button.depends_on == ()
        assert "Button" in todo_list.depends_on
        assert "TodoList" in home.depends_on

    def test_full_extraction(self) -> None:
        handoff = _handoff(
            db_entities=[_entity("User")],
            endpoints=[_endpoint("GET", "/api/users")],
            ui_components=[_component("UserList")],
        )
        units = extract_atomic_units(handoff, None)
        kinds = {u.kind for u in units}
        assert kinds == {
            AtomicUnitKind.SCAFFOLDING,
            AtomicUnitKind.DATABASE_ENTITY,
            AtomicUnitKind.BACKEND_ENDPOINT,
            AtomicUnitKind.FRONTEND_COMPONENT,
        }


# ── topological_sort_units ───────────────────────────────────────────


class TestTopologicalSort:
    def test_respects_dependencies(self) -> None:
        units = [
            AtomicUnitSpec(
                kind=AtomicUnitKind.DATABASE_ENTITY,
                name="Post",
                depends_on=("User",),
                phase=1,
            ),
            AtomicUnitSpec(
                kind=AtomicUnitKind.DATABASE_ENTITY,
                name="User",
                phase=1,
            ),
        ]
        sorted_units = topological_sort_units(units)
        names = [u.name for u in sorted_units]
        assert names.index("User") < names.index("Post")

    def test_sorts_by_phase(self) -> None:
        units = [
            AtomicUnitSpec(
                kind=AtomicUnitKind.FRONTEND_COMPONENT,
                name="App",
                phase=3,
            ),
            AtomicUnitSpec(
                kind=AtomicUnitKind.SCAFFOLDING,
                name="scaffold",
                phase=0,
            ),
            AtomicUnitSpec(
                kind=AtomicUnitKind.DATABASE_ENTITY,
                name="User",
                phase=1,
            ),
        ]
        sorted_units = topological_sort_units(units)
        phases = [u.phase for u in sorted_units]
        assert phases == sorted(phases)

    def test_secondary_sort_by_name(self) -> None:
        units = [
            AtomicUnitSpec(
                kind=AtomicUnitKind.DATABASE_ENTITY,
                name="Zebra",
                phase=1,
            ),
            AtomicUnitSpec(
                kind=AtomicUnitKind.DATABASE_ENTITY,
                name="Alpha",
                phase=1,
            ),
        ]
        sorted_units = topological_sort_units(units)
        names = [u.name for u in sorted_units]
        assert names == ["Alpha", "Zebra"]

    def test_ignores_unknown_deps(self) -> None:
        units = [
            AtomicUnitSpec(
                kind=AtomicUnitKind.DATABASE_ENTITY,
                name="Post",
                depends_on=("NonExistent",),
                phase=1,
            ),
        ]
        sorted_units = topological_sort_units(units)
        assert len(sorted_units) == 1


# ── _is_auth_endpoint ────────────────────────────────────────────────


class TestIsAuthEndpoint:
    @pytest.mark.parametrize(
        ("path", "summary"),
        [
            ("/api/auth/login", ""),
            ("/api/register", "Register user"),
            ("/api/token/refresh", ""),
            ("/api/signup", ""),
            ("/api/sessions", "Create session"),
        ],
    )
    def test_detects_auth(self, path: str, summary: str) -> None:
        assert _is_auth_endpoint(path, summary) is True

    @pytest.mark.parametrize(
        ("path", "summary"),
        [
            ("/api/todos", "List todos"),
            ("/api/users/me", "Get profile"),
        ],
    )
    def test_non_auth(self, path: str, summary: str) -> None:
        assert _is_auth_endpoint(path, summary) is False


# ── _classify_file_domain ────────────────────────────────────────────


class TestClassifyFileDomain:
    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            ("migrations/001.sql", "database"),
            ("src/models/user.py", "database"),
            ("prisma/schema.prisma", "database"),
            ("src/components/Button.tsx", "frontend"),
            ("src/pages/index.tsx", "frontend"),
            ("src/app/layout.tsx", "frontend"),
            ("src/routes/todos.py", "backend"),
            ("src/middleware/auth.py", "backend"),
            ("package.json", "scaffold"),
            ("docker-compose.yml", "scaffold"),
        ],
    )
    def test_classification(self, path: str, expected: str) -> None:
        assert _classify_file_domain(path) == expected


# ── _extract_signatures ──────────────────────────────────────────────


class TestExtractSignatures:
    def test_extracts_python_functions(self) -> None:
        content = "def foo(x: int) -> str:\n    return str(x)\n\ndef bar():\n    pass"
        result = _extract_signatures(content)
        assert "def foo" in result
        assert "def bar" in result

    def test_extracts_class_definitions(self) -> None:
        content = "class User:\n    name: str\n    email: str"
        result = _extract_signatures(content)
        assert "class User" in result

    def test_fallback_for_no_signatures(self) -> None:
        content = "x = 1\ny = 2"
        result = _extract_signatures(content)
        assert result == content[:200]


# ── build_incremental_context ────────────────────────────────────────


class TestBuildIncrementalContext:
    def test_includes_design_context(self) -> None:
        spec = AtomicUnitSpec(
            kind=AtomicUnitKind.BACKEND_ENDPOINT,
            name="GET /api/test",
            phase=2,
        )
        result = build_incremental_context("# Design", [], spec)
        assert "# Design" in result

    def test_includes_unit_spec(self) -> None:
        spec = AtomicUnitSpec(
            kind=AtomicUnitKind.BACKEND_ENDPOINT,
            name="GET /api/test",
            endpoint_spec=_endpoint("GET", "/api/test", summary="Test endpoint"),
            phase=2,
        )
        result = build_incremental_context("# Design", [], spec)
        assert "GET /api/test" in result

    def test_tiered_context(self) -> None:
        spec = AtomicUnitSpec(
            kind=AtomicUnitKind.BACKEND_ENDPOINT,
            name="test",
            phase=2,
        )
        files = [
            _file(
                "src/routes/existing.py",
                "def handler(): pass",
                "python",
            ),
            _file(
                "migrations/001.sql",
                "CREATE TABLE x (id INT);",
                "sql",
            ),
            _file(
                "src/components/App.tsx",
                "export default App",
                "typescript",
            ),
        ]
        result = build_incremental_context("# Design", files, spec)
        # tier 1: full content for same domain
        assert "def handler(): pass" in result
        # tier 3: at least path present for distant domain
        assert "App.tsx" in result

    def test_respects_budget(self) -> None:
        spec = AtomicUnitSpec(
            kind=AtomicUnitKind.BACKEND_ENDPOINT,
            name="test",
            phase=2,
        )
        result = build_incremental_context("# Design", [], spec, max_context_chars=100)
        assert len(result) <= 200


# ── filter_findings_to_paths ─────────────────────────────────────────


class TestFilterFindingsToPath:
    def test_filters_to_matching_paths(self) -> None:
        report = VerificationReport(
            findings=[
                VerificationFinding(
                    category="lint",
                    severity="HIGH",
                    file_path="a.py",
                    message="err1",
                ),
                VerificationFinding(
                    category="type",
                    severity="MEDIUM",
                    file_path="b.py",
                    message="err2",
                ),
                VerificationFinding(
                    category="build",
                    severity="LOW",
                    file_path="c.py",
                    message="err3",
                ),
            ],
            lint_passed=False,
            type_check_passed=False,
            build_passed=False,
        )
        filtered = filter_findings_to_paths(report, {"a.py", "c.py"})
        assert len(filtered.findings) == 2
        assert filtered.lint_passed is False
        assert filtered.type_check_passed is True
        assert filtered.build_passed is False

    def test_empty_paths_returns_clean(self) -> None:
        report = VerificationReport(
            findings=[
                VerificationFinding(
                    category="lint",
                    severity="HIGH",
                    file_path="a.py",
                    message="err",
                ),
            ],
            lint_passed=False,
        )
        filtered = filter_findings_to_paths(report, set())
        assert len(filtered.findings) == 0
        assert filtered.lint_passed is True


# ── AtomicGenerationProgress ─────────────────────────────────────────


class TestAtomicGenerationProgress:
    def test_add_verified_result(self) -> None:
        progress = AtomicGenerationProgress()
        spec = AtomicUnitSpec(
            kind=AtomicUnitKind.SCAFFOLDING,
            name="scaffold",
            phase=0,
        )
        output = AtomicScaffoldUnit(
            files=[_file("package.json", "{}", "json")],
            packages=["react"],
            env_vars=["API_KEY"],
        )
        result = AtomicUnitResult(spec=spec, output=output, verified=True)
        progress.add_result(result)
        assert len(progress.completed) == 1
        assert len(progress.failed) == 0
        assert len(progress.all_files) == 1
        assert "react" in progress.all_packages
        assert "API_KEY" in progress.all_env_vars

    def test_add_failed_result(self) -> None:
        progress = AtomicGenerationProgress()
        spec = AtomicUnitSpec(
            kind=AtomicUnitKind.DATABASE_ENTITY,
            name="User",
            phase=1,
        )
        output = AtomicDatabaseUnit(files=[_file()])
        result = AtomicUnitResult(spec=spec, output=output, verified=False)
        progress.add_result(result)
        assert len(progress.completed) == 0
        assert len(progress.failed) == 1

    def test_deduplicates_packages_and_env_vars(self) -> None:
        progress = AtomicGenerationProgress()
        spec1 = AtomicUnitSpec(kind=AtomicUnitKind.SCAFFOLDING, name="s1", phase=0)
        spec2 = AtomicUnitSpec(kind=AtomicUnitKind.SCAFFOLDING, name="s2", phase=0)
        for spec in [spec1, spec2]:
            out = AtomicScaffoldUnit(packages=["react"], env_vars=["API_KEY"])
            progress.add_result(AtomicUnitResult(spec=spec, output=out, verified=True))
        assert progress.all_packages.count("react") == 1
        assert progress.all_env_vars.count("API_KEY") == 1


# ── _progress_to_agent_results ───────────────────────────────────────


class TestProgressToAgentResults:
    def test_classifies_by_kind(self) -> None:
        progress = AtomicGenerationProgress()

        # Scaffold
        progress.add_result(
            AtomicUnitResult(
                spec=AtomicUnitSpec(
                    kind=AtomicUnitKind.SCAFFOLDING,
                    name="scaffold",
                    phase=0,
                ),
                output=AtomicScaffoldUnit(files=[_file("src/scaffold.py")]),
                verified=True,
            )
        )
        # Database entity
        progress.add_result(
            AtomicUnitResult(
                spec=AtomicUnitSpec(
                    kind=AtomicUnitKind.DATABASE_ENTITY,
                    name="User",
                    entity_spec=_entity("User"),
                    phase=1,
                ),
                output=AtomicDatabaseUnit(files=[_file("src/User.py")]),
                verified=True,
            )
        )
        # Backend endpoint
        progress.add_result(
            AtomicUnitResult(
                spec=AtomicUnitSpec(
                    kind=AtomicUnitKind.BACKEND_ENDPOINT,
                    name="GET /api/users",
                    endpoint_spec=_endpoint("GET", "/api/users"),
                    phase=2,
                ),
                output=AtomicBackendUnit(files=[_file("src/GET /api/users.py")]),
                verified=True,
            )
        )
        # Frontend component
        progress.add_result(
            AtomicUnitResult(
                spec=AtomicUnitSpec(
                    kind=AtomicUnitKind.FRONTEND_COMPONENT,
                    name="UserList",
                    phase=3,
                ),
                output=AtomicFrontendUnit(files=[_file("src/UserList.py")]),
                verified=True,
            )
        )

        frontend, backend, database = _progress_to_agent_results(progress)
        assert len(frontend.files) == 1
        # Backend gets scaffold + endpoint files
        assert len(backend.files) == 2
        assert len(database.files) == 1
        assert "GET /api/users" in backend.implemented_endpoints
        assert "User" in database.entities_created


# ── verify_and_fix_unit ──────────────────────────────────────────────


class TestVerifyAndFixUnit:
    @pytest.mark.asyncio
    async def test_passes_clean_unit(self) -> None:
        spec = AtomicUnitSpec(
            kind=AtomicUnitKind.SCAFFOLDING,
            name="scaffold",
            phase=0,
        )
        output = AtomicScaffoldUnit(files=[_file("config.json", "{}", "json")])
        unit_result = AtomicUnitResult(spec=spec, output=output)

        with patch(
            "colette.stages.implementation.atomic.verify_generated_code",
            new_callable=AsyncMock,
            return_value=_clean_report(),
        ):
            result = await verify_and_fix_unit(unit_result, [], settings=_mock_settings())
            assert result.verified is True
            assert result.fix_attempts == 0

    @pytest.mark.asyncio
    async def test_empty_files_auto_verified(self) -> None:
        spec = AtomicUnitSpec(
            kind=AtomicUnitKind.SCAFFOLDING,
            name="scaffold",
            phase=0,
        )
        output = AtomicScaffoldUnit(files=[])
        unit_result = AtomicUnitResult(spec=spec, output=output)

        result = await verify_and_fix_unit(unit_result, [], settings=_mock_settings())
        assert result.verified is True

    @pytest.mark.asyncio
    async def test_fix_attempt_on_failure(self) -> None:
        spec = AtomicUnitSpec(
            kind=AtomicUnitKind.SCAFFOLDING,
            name="scaffold",
            phase=0,
        )
        f = _file("src/main.py", "bad code")
        output = AtomicScaffoldUnit(files=[f])
        unit_result = AtomicUnitResult(spec=spec, output=output)

        bad_report = VerificationReport(
            findings=[
                VerificationFinding(
                    category="lint",
                    severity="HIGH",
                    file_path="src/main.py",
                    message="syntax error",
                )
            ],
            lint_passed=False,
            type_check_passed=True,
            build_passed=True,
        )

        with (
            patch(
                "colette.stages.implementation.atomic.verify_generated_code",
                new_callable=AsyncMock,
                side_effect=[bad_report, _clean_report()],
            ),
            patch(
                "colette.stages.implementation.verifier.fix_files",
                new_callable=AsyncMock,
                return_value=[_file("src/main.py", "fixed code")],
            ),
        ):
            result = await verify_and_fix_unit(
                unit_result,
                [],
                settings=_mock_settings(),
                max_fix_attempts=2,
            )
            assert result.verified is True
            assert result.fix_attempts == 1


# ── run_atomic_generation (integration-style) ────────────────────────


class TestRunAtomicGeneration:
    @pytest.mark.asyncio
    async def test_generates_all_phases(self) -> None:
        handoff = _handoff(
            db_entities=[_entity("User")],
            endpoints=[_endpoint("GET", "/api/users")],
            ui_components=[_component("UserList")],
        )

        scaffold_out = AtomicScaffoldUnit(files=[_file("package.json", "{}", "json")])
        db_out = AtomicDatabaseUnit(files=[_file("models/user.py")])
        backend_out = AtomicBackendUnit(files=[_file("routes/users.py")])
        frontend_out = AtomicFrontendUnit(
            files=[
                _file(
                    "components/UserList.tsx",
                    lang="typescript",
                )
            ]
        )

        generate_side = [
            scaffold_out,
            db_out,
            backend_out,
            frontend_out,
        ]

        with (
            patch(
                "colette.stages.implementation.atomic.invoke_structured",
                new_callable=AsyncMock,
                side_effect=generate_side,
            ),
            patch(
                "colette.stages.implementation.atomic.verify_generated_code",
                new_callable=AsyncMock,
                return_value=_clean_report(),
            ),
        ):
            progress = await run_atomic_generation(
                handoff, "# Design", None, settings=_mock_settings()
            )
            assert len(progress.completed) == 4
            assert len(progress.failed) == 0
            assert len(progress.all_files) == 4

    @pytest.mark.asyncio
    async def test_handles_generation_failure(self) -> None:
        handoff = _handoff(db_entities=[_entity("User")])
        scaffold_out = AtomicScaffoldUnit(files=[_file("package.json", "{}", "json")])

        with (
            patch(
                "colette.stages.implementation.atomic.invoke_structured",
                new_callable=AsyncMock,
                side_effect=[
                    scaffold_out,
                    RuntimeError("LLM timeout"),
                ],
            ),
            patch(
                "colette.stages.implementation.atomic.verify_generated_code",
                new_callable=AsyncMock,
                return_value=_clean_report(),
            ),
        ):
            progress = await run_atomic_generation(
                handoff, "# Design", None, settings=_mock_settings()
            )
            assert len(progress.completed) == 1  # scaffold
            assert len(progress.failed) == 1  # User entity


# ── Helpers ──────────────────────────────────────────────────────────


def _mock_settings() -> object:
    """Minimal mock settings for tests."""

    class _Settings:
        use_atomic_generation: bool = True
        atomic_max_fix_attempts: int = 2
        openrouter_api_key: str = "test"
        default_execution_model: str = "test-model"
        default_validation_model: str = "test-model"
        default_reasoning_model: str = "test-model"
        llm_timeout_seconds: int = 30
        llm_max_retries: int = 1
        llm_max_concurrency: int = 2
        prompt_caching_enabled: bool = False
        specialist_context_budget: int = 60_000

    return _Settings()

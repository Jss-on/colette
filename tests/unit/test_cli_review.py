"""Tests for cli_review.py — Textual TUI approval review app."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from colette.cli_review import _LEXER_MAP, ApprovalReviewApp, _get

# ── Helper tests ─────────────────────────────────────────────────────


class TestGetHelper:
    def test_returns_value_from_dict(self) -> None:
        assert _get({"a": 1}, "a") == 1

    def test_returns_default_from_dict_missing_key(self) -> None:
        assert _get({"a": 1}, "b", "fallback") == "fallback"

    def test_returns_default_for_non_dict(self) -> None:
        assert _get(42, "anything", "default") == "default"

    def test_returns_empty_string_default(self) -> None:
        assert _get({}, "x") == ""

    def test_returns_default_for_none(self) -> None:
        assert _get(None, "key", "fb") == "fb"


class TestLexerMap:
    def test_known_languages(self) -> None:
        assert _LEXER_MAP["python"] == "python"
        assert _LEXER_MAP["typescript"] == "typescript"
        assert _LEXER_MAP["shell"] == "bash"

    def test_not_in_map(self) -> None:
        assert "rust" not in _LEXER_MAP


# ── ApprovalReviewApp init ───────────────────────────────────────────


def _make_approval(
    stage: str = "requirements",
    tier: str = "T2_MODERATE",
    score: float | None = 0.75,
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "tier": tier,
        "confidence_score": score,
        "request_id": "req-001",
        "handoff_summary": summary or {"stage": stage},
    }


class TestApprovalReviewAppInit:
    def test_basic_init(self) -> None:
        data = _make_approval()
        app = ApprovalReviewApp(data)
        assert app._stage == "requirements"
        assert app._approval is data

    def test_stage_from_summary_fallback(self) -> None:
        data: dict[str, Any] = {
            "handoff_summary": {"stage": "design"},
            "tier": "T1",
        }
        app = ApprovalReviewApp(data)
        assert app._stage == "design"

    def test_missing_stage_defaults_to_question_mark(self) -> None:
        app = ApprovalReviewApp({})
        assert app._stage == "?"

    def test_bindings_defined(self) -> None:
        assert len(ApprovalReviewApp.BINDINGS) == 3


# ── Tab builders (unit-test the logic without running Textual) ───────


class TestBuildTabs:
    """Test _build_tabs returns correct panes for each stage."""

    def _app_with_stage(self, stage: str, summary: dict[str, Any]) -> ApprovalReviewApp:
        data = _make_approval(stage=stage, summary={**summary, "stage": stage})
        return ApprovalReviewApp(data)

    def test_empty_summary_gives_info_pane(self) -> None:
        app = self._app_with_stage("requirements", {})
        panes = app._build_tabs()
        assert len(panes) == 1  # fallback "Info" pane

    def test_requirements_with_stories(self) -> None:
        app = self._app_with_stage(
            "requirements",
            {
                "user_stories": [
                    {
                        "id": "US-1",
                        "title": "Login",
                        "priority": "MUST",
                        "acceptance_criteria": ["AC1", "AC2"],
                    },
                ],
            },
        )
        panes = app._build_tabs()
        assert len(panes) >= 1

    def test_requirements_with_nfrs(self) -> None:
        app = self._app_with_stage(
            "requirements",
            {
                "nfrs": [
                    {"id": "NFR-1", "category": "perf", "description": "desc", "target": "99%"}
                ],
            },
        )
        panes = app._build_tabs()
        assert len(panes) >= 1

    def test_requirements_with_constraints(self) -> None:
        app = self._app_with_stage(
            "requirements",
            {
                "tech_constraints": [
                    {"id": "TC-1", "description": "Use Python", "rationale": "Team expertise"},
                ],
            },
        )
        panes = app._build_tabs()
        assert len(panes) >= 1

    def test_design_with_endpoints(self) -> None:
        app = self._app_with_stage(
            "design",
            {
                "endpoints": [
                    {
                        "method": "GET",
                        "path": "/api/v1/items",
                        "summary": "List items",
                        "auth_required": True,
                    },
                ],
            },
        )
        panes = app._build_tabs()
        assert len(panes) >= 1

    def test_design_with_entities(self) -> None:
        app = self._app_with_stage(
            "design",
            {
                "db_entities": [
                    {
                        "name": "User",
                        "fields": [{"name": "id", "type": "uuid"}],
                        "indexes": ["pk_user"],
                        "relationships": ["has_many posts"],
                    },
                ],
            },
        )
        panes = app._build_tabs()
        assert len(panes) >= 1

    def test_design_with_components(self) -> None:
        app = self._app_with_stage(
            "design",
            {
                "ui_components": [
                    {
                        "name": "LoginForm",
                        "description": "A form",
                        "route": "/login",
                        "children": ["Button"],
                    },
                ],
            },
        )
        panes = app._build_tabs()
        assert len(panes) >= 1

    def test_design_with_tech_stack(self) -> None:
        app = self._app_with_stage(
            "design",
            {
                "tech_stack": {"backend": "Python", "db": "Postgres"},
            },
        )
        panes = app._build_tabs()
        assert len(panes) >= 1

    def test_design_with_adrs(self) -> None:
        app = self._app_with_stage(
            "design",
            {
                "adrs": [
                    {
                        "id": "ADR-1",
                        "title": "Use REST",
                        "status": "accepted",
                        "context": "...",
                        "decision": "REST API",
                        "alternatives": ["GraphQL"],
                    }
                ],
            },
        )
        panes = app._build_tabs()
        assert len(panes) >= 1

    def test_design_with_openapi_spec(self) -> None:
        app = self._app_with_stage(
            "design",
            {
                "openapi_spec": '{"openapi":"3.0.0"}',
            },
        )
        panes = app._build_tabs()
        assert len(panes) >= 1

    def test_design_with_text_panes(self) -> None:
        app = self._app_with_stage(
            "design",
            {
                "architecture_summary": "Microservices arch",
                "security_design": "OAuth 2.0",
            },
        )
        panes = app._build_tabs()
        assert len(panes) == 2

    def test_implementation_with_gen_files(self) -> None:
        app = self._app_with_stage(
            "implementation",
            {
                "generated_files": [
                    {"path": "main.py", "language": "python", "content": "print('hi')"},
                ],
            },
        )
        panes = app._build_tabs()
        assert len(panes) >= 1

    def test_implementation_with_files(self) -> None:
        app = self._app_with_stage(
            "implementation",
            {
                "files": [{"path": "x.py", "language": "python", "lines_added": 10}],
            },
        )
        panes = app._build_tabs()
        assert len(panes) >= 1

    def test_testing_with_gen_files(self) -> None:
        app = self._app_with_stage(
            "testing",
            {
                "generated_files": [
                    {"path": "test_x.py", "language": "python", "content": ""},
                ],
            },
        )
        panes = app._build_tabs()
        assert len(panes) >= 1

    def test_testing_with_findings(self) -> None:
        app = self._app_with_stage(
            "testing",
            {
                "security_findings": [
                    {"severity": "HIGH", "category": "XSS", "description": "Reflected XSS"},
                ],
            },
        )
        panes = app._build_tabs()
        assert len(panes) >= 1

    def test_deployment_with_gen_files(self) -> None:
        app = self._app_with_stage(
            "deployment",
            {
                "generated_files": [
                    {
                        "path": "Dockerfile",
                        "language": "dockerfile",
                        "content": "FROM python:3.12",
                    },
                ],
            },
        )
        panes = app._build_tabs()
        assert len(panes) >= 1

    def test_staging_with_gen_files(self) -> None:
        app = self._app_with_stage(
            "staging",
            {
                "generated_files": [
                    {"path": "k8s.yaml", "language": "yaml", "content": ""},
                ],
            },
        )
        panes = app._build_tabs()
        assert len(panes) >= 1

    def test_unknown_stage_gets_info_pane(self) -> None:
        app = self._app_with_stage("unknown_stage", {})
        panes = app._build_tabs()
        assert len(panes) == 1  # info pane


# ── Pane factory methods ─────────────────────────────────────────────


class TestPaneFactories:
    def test_table_pane(self) -> None:
        pane = ApprovalReviewApp._table_pane("Test", "t1", ["Col1", "Col2"], [("a", "b")])
        assert pane.id == "t1"

    def test_richlog_pane(self) -> None:
        pane = ApprovalReviewApp._richlog_pane("Test", "r1", "hello")
        assert pane.id == "r1"

    def test_syntax_pane(self) -> None:
        pane = ApprovalReviewApp._syntax_pane("Code", "s1", "print('hi')", "python")
        assert pane.id == "s1"

    def test_text_pane(self) -> None:
        pane = ApprovalReviewApp._text_pane("Notes", "n1", "Some text")
        assert pane.id == "n1"

    def test_files_pane(self) -> None:
        app = ApprovalReviewApp(_make_approval())
        pane = app._files_pane(
            "Files",
            "f1",
            [
                {"path": "a.py", "language": "python", "content": "x = 1"},
            ],
        )
        assert pane.id == "f1"

    def test_files_pane_empty_content(self) -> None:
        app = ApprovalReviewApp(_make_approval())
        pane = app._files_pane(
            "Files",
            "f2",
            [
                {"path": "empty.py", "language": "python"},
            ],
        )
        assert pane.id == "f2"


# ── Format ADRs ──────────────────────────────────────────────────────


class TestFormatAdrs:
    def test_basic_adr(self) -> None:
        result = ApprovalReviewApp._format_adrs(
            [
                {"id": "ADR-1", "title": "Use REST", "status": "accepted"},
            ]
        )
        assert "ADR-1" in result
        assert "Use REST" in result
        assert "accepted" in result

    def test_adr_with_context_and_decision(self) -> None:
        result = ApprovalReviewApp._format_adrs(
            [
                {
                    "id": "ADR-2",
                    "title": "DB Choice",
                    "status": "proposed",
                    "context": "Need ACID",
                    "decision": "PostgreSQL",
                },
            ]
        )
        assert "Need ACID" in result
        assert "PostgreSQL" in result

    def test_adr_with_alternatives(self) -> None:
        result = ApprovalReviewApp._format_adrs(
            [
                {
                    "id": "ADR-3",
                    "title": "API",
                    "status": "accepted",
                    "alternatives": ["gRPC", "WebSocket"],
                },
            ]
        )
        assert "gRPC" in result
        assert "WebSocket" in result

    def test_empty_adrs(self) -> None:
        result = ApprovalReviewApp._format_adrs([])
        assert result == ""

    def test_adr_context_truncated(self) -> None:
        long_ctx = "x" * 500
        formatted = ApprovalReviewApp._format_adrs(
            [
                {"id": "A", "title": "T", "status": "s", "context": long_ctx},
            ]
        )
        # Context should be truncated to 300 chars in the output
        assert long_ctx[:300] in formatted
        assert long_ctx[:301] not in formatted


# ── Action methods ───────────────────────────────────────────────────


class TestActions:
    def test_action_approve(self) -> None:
        app = ApprovalReviewApp(_make_approval())
        with patch.object(app, "exit") as mock_exit:
            app.action_approve()
            mock_exit.assert_called_once_with("approved")

    def test_action_reject(self) -> None:
        app = ApprovalReviewApp(_make_approval())
        with patch.object(app, "exit") as mock_exit:
            app.action_reject()
            mock_exit.assert_called_once_with("rejected")

    def test_action_quit_app(self) -> None:
        app = ApprovalReviewApp(_make_approval())
        with patch.object(app, "exit") as mock_exit:
            app.action_quit_app()
            mock_exit.assert_called_once_with("rejected")

    def test_on_button_pressed_approve(self) -> None:
        app = ApprovalReviewApp(_make_approval())
        event = MagicMock()
        event.button.id = "approve"
        with patch.object(app, "exit") as mock_exit:
            app.on_button_pressed(event)
            mock_exit.assert_called_once_with("approved")

    def test_on_button_pressed_reject(self) -> None:
        app = ApprovalReviewApp(_make_approval())
        event = MagicMock()
        event.button.id = "reject"
        with patch.object(app, "exit") as mock_exit:
            app.on_button_pressed(event)
            mock_exit.assert_called_once_with("rejected")

    def test_on_button_pressed_unknown(self) -> None:
        app = ApprovalReviewApp(_make_approval())
        event = MagicMock()
        event.button.id = "unknown"
        with patch.object(app, "exit") as mock_exit:
            app.on_button_pressed(event)
            mock_exit.assert_not_called()

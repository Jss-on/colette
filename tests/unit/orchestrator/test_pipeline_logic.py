"""Tests for pipeline internals — gate nodes, stage nodes, routing, helpers."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from colette.orchestrator.pipeline import (
    _gate_router,
    _make_gate_node,
    _make_stage_node,
    _next_stage,
    _summarize_handoff_for_review,
)

# ── _next_stage ──────────────────────────────────────────────────────


class TestNextStage:
    def test_returns_next_stage(self) -> None:
        result = _next_stage("requirements", [])
        assert result == "design"

    def test_returns_none_for_last(self) -> None:
        result = _next_stage("monitoring", [])
        assert result is None

    def test_skips_stages(self) -> None:
        result = _next_stage("requirements", ["design"])
        assert result == "implementation"

    def test_skips_all_remaining(self) -> None:
        result = _next_stage(
            "requirements",
            ["design", "implementation", "testing", "deployment", "monitoring"],
        )
        assert result is None


# ── _summarize_handoff_for_review ────────────────────────────────────


class TestSummarizeHandoff:
    def test_empty_handoff(self) -> None:
        state: dict[str, Any] = {"handoffs": {}}
        result = _summarize_handoff_for_review("requirements", state)
        assert result["stage"] == "requirements"
        assert "note" in result

    def test_requirements_stage(self) -> None:
        state: dict[str, Any] = {
            "handoffs": {
                "requirements": {
                    "functional_requirements": [{"id": "US-1"}],
                    "nonfunctional_requirements": [{"id": "NFR-1"}],
                    "tech_constraints": [{"id": "TC-1"}],
                    "completeness_score": 0.85,
                },
            },
            "metadata": {},
        }
        result = _summarize_handoff_for_review("requirements", state)
        assert len(result["user_stories"]) == 1
        assert len(result["nfrs"]) == 1
        assert result["completeness_score"] == 0.85

    def test_design_stage(self) -> None:
        state: dict[str, Any] = {
            "handoffs": {
                "design": {
                    "tech_stack": {"backend": "Python"},
                    "endpoints": [{"path": "/api"}],
                    "db_entities": [],
                    "ui_components": [],
                    "adrs": [],
                    "openapi_spec": "{}",
                    "architecture_summary": "micro",
                    "security_design": "oauth",
                },
            },
            "metadata": {},
        }
        result = _summarize_handoff_for_review("design", state)
        assert result["tech_stack"]["backend"] == "Python"
        assert len(result["endpoints"]) == 1
        assert result["openapi_spec"] == "{}"

    def test_implementation_stage(self) -> None:
        state: dict[str, Any] = {
            "handoffs": {
                "implementation": {
                    "files_changed": [{"path": "a.py"}, {"path": "b.py"}],
                    "packages": ["fastapi"],
                },
            },
            "metadata": {},
        }
        result = _summarize_handoff_for_review("implementation", state)
        assert result["file_count"] == 2
        assert "fastapi" in result["packages"]

    def test_implementation_with_generated_files(self) -> None:
        state: dict[str, Any] = {
            "handoffs": {
                "implementation": {
                    "files_changed": [{"path": "x.py"}],
                    "packages": [],
                },
            },
            "metadata": {
                "generated_files": {
                    "implementation": [
                        {"path": "main.py", "content": "..."},
                    ],
                },
            },
        }
        result = _summarize_handoff_for_review("implementation", state)
        assert len(result["generated_files"]) == 1

    def test_testing_stage(self) -> None:
        state: dict[str, Any] = {
            "handoffs": {
                "testing": {
                    "test_files": [{"path": "test_a.py"}],
                    "coverage_metrics": {"line_coverage_pct": 85},
                    "security_findings": [
                        {"severity": "HIGH", "description": "XSS"},
                    ],
                },
            },
            "metadata": {},
        }
        result = _summarize_handoff_for_review("testing", state)
        assert result["line_coverage"] == 85
        assert len(result["security_findings"]) == 1

    def test_deployment_stage(self) -> None:
        state: dict[str, Any] = {
            "handoffs": {
                "deployment": {
                    "deploy_target": "k8s",
                    "container_image": "app:latest",
                    "deployment_configs": [{"name": "prod"}],
                },
            },
            "metadata": {},
        }
        result = _summarize_handoff_for_review("staging", state)
        assert result["deploy_target"] == "k8s"
        assert result["container_image"] == "app:latest"

    def test_unknown_gate_no_crash(self) -> None:
        state: dict[str, Any] = {"handoffs": {"unknown": {"foo": "bar"}}}
        result = _summarize_handoff_for_review("unknown", state)
        assert result["stage"] == "unknown"


# ── _gate_router ─────────────────────────────────────────────────────


class TestGateRouter:
    def test_passed_routes_to_next_stage(self) -> None:
        router = _gate_router("requirements", "requirements", [])
        state: dict[str, Any] = {
            "quality_gate_results": {
                "requirements": {"passed": True},
            },
        }
        assert router(state) == "stage_design"

    def test_failed_routes_to_gate_failed(self) -> None:
        router = _gate_router("requirements", "requirements", [])
        state: dict[str, Any] = {
            "quality_gate_results": {
                "requirements": {"passed": False},
            },
        }
        assert router(state) == "gate_failed"

    def test_last_gate_routes_to_end(self) -> None:
        router = _gate_router("staging", "deployment", [])
        state: dict[str, Any] = {
            "quality_gate_results": {
                "staging": {"passed": True},
            },
        }
        assert router(state) == "stage_monitoring"

    def test_skipped_stages(self) -> None:
        router = _gate_router("requirements", "requirements", [])
        state: dict[str, Any] = {
            "quality_gate_results": {
                "requirements": {"passed": True},
            },
            "skip_stages": ["design"],
        }
        assert router(state) == "stage_implementation"

    def test_missing_gate_result(self) -> None:
        router = _gate_router("requirements", "requirements", [])
        state: dict[str, Any] = {"quality_gate_results": {}}
        assert router(state) == "gate_failed"


# ── _make_stage_node ─────────────────────────────────────────────────


class TestMakeStageNode:
    @pytest.mark.asyncio
    async def test_stage_node_runs_and_emits_events(self) -> None:
        bus = MagicMock()
        with patch(
            "colette.orchestrator.pipeline._STAGE_RUNNERS",
            {"requirements": AsyncMock(return_value={"result": "ok"})},
        ):
            node = _make_stage_node("requirements", event_bus=bus)
            result = await node(
                {"project_id": "p1", "stage_statuses": {}, "started_at": ""}
            )
        assert result == {"result": "ok"}
        assert bus.emit.call_count == 2  # STARTED + COMPLETED

    @pytest.mark.asyncio
    async def test_stage_node_emits_failed_on_error(self) -> None:
        bus = MagicMock()
        with patch(
            "colette.orchestrator.pipeline._STAGE_RUNNERS",
            {"requirements": AsyncMock(side_effect=RuntimeError("boom"))},
        ):
            node = _make_stage_node("requirements", event_bus=bus)
            with pytest.raises(RuntimeError, match="boom"):
                await node(
                    {"project_id": "p1", "stage_statuses": {}, "started_at": ""}
                )
        # STARTED + FAILED
        assert bus.emit.call_count == 2

    @pytest.mark.asyncio
    async def test_stage_node_without_bus(self) -> None:
        with patch(
            "colette.orchestrator.pipeline._STAGE_RUNNERS",
            {"requirements": AsyncMock(return_value={"ok": True})},
        ):
            node = _make_stage_node("requirements", event_bus=None)
            result = await node(
                {"project_id": "p1", "stage_statuses": {}, "started_at": ""}
            )
        assert result == {"ok": True}


# ── _make_gate_node ──────────────────────────────────────────────────


class TestMakeGateNode:
    @pytest.mark.asyncio
    async def test_gate_passed_auto_approve(self) -> None:
        """T3 tier gates auto-approve without interrupting."""
        from colette.config import Settings
        from colette.gates.base import GateRegistry

        mock_gate = AsyncMock()
        mock_result = MagicMock()
        mock_result.passed = True
        mock_result.score = 0.95
        mock_result.failure_reasons = []
        mock_result.criteria_results = {}
        mock_result.model_dump.return_value = {
            "passed": True, "score": 0.95,
        }

        registry = MagicMock(spec=GateRegistry)
        registry.get.return_value = mock_gate
        settings = Settings()
        bus = MagicMock()

        with patch(
            "colette.orchestrator.pipeline.evaluate_gate",
            return_value=mock_result,
        ), patch(
            "colette.orchestrator.pipeline.determine_approval_action",
            return_value="auto_approve",
        ):
            node = _make_gate_node("requirements", registry, settings, bus)
            result = await node({
                "project_id": "p1",
                "quality_gate_results": {},
                "started_at": "",
            })

        assert "requirements" in result["quality_gate_results"]
        # Should emit GATE_PASSED
        assert bus.emit.call_count >= 1

    @pytest.mark.asyncio
    async def test_gate_failed(self) -> None:
        from colette.config import Settings
        from colette.gates.base import GateRegistry

        mock_result = MagicMock()
        mock_result.passed = False
        mock_result.score = 0.3
        mock_result.failure_reasons = ["low quality"]
        mock_result.model_dump.return_value = {
            "passed": False, "score": 0.3,
        }

        registry = MagicMock(spec=GateRegistry)
        settings = Settings()
        bus = MagicMock()

        with patch(
            "colette.orchestrator.pipeline.evaluate_gate",
            return_value=mock_result,
        ):
            node = _make_gate_node("requirements", registry, settings, bus)
            result = await node({
                "project_id": "p1",
                "quality_gate_results": {},
                "started_at": "",
            })

        gate_result = result["quality_gate_results"]["requirements"]
        assert gate_result["passed"] is False

    @pytest.mark.asyncio
    async def test_gate_passed_interrupt(self) -> None:
        """T1 tier gates should interrupt for human approval."""
        from colette.config import Settings
        from colette.gates.base import GateRegistry

        mock_result = MagicMock()
        mock_result.passed = True
        mock_result.score = 0.7
        mock_result.failure_reasons = []
        mock_result.criteria_results = {}
        mock_result.model_dump.return_value = {
            "passed": True, "score": 0.7,
        }

        registry = MagicMock(spec=GateRegistry)
        settings = Settings()
        bus = MagicMock()

        mock_approval = MagicMock()
        mock_approval.request_id = "req-123"
        mock_approval.model_dump.return_value = {"request_id": "req-123"}

        with patch(
            "colette.orchestrator.pipeline.evaluate_gate",
            return_value=mock_result,
        ), patch(
            "colette.orchestrator.pipeline.determine_approval_action",
            return_value="interrupt",
        ), patch(
            "colette.orchestrator.pipeline.create_approval_request",
            return_value=mock_approval,
        ), patch(
            "colette.orchestrator.pipeline.interrupt",
        ) as mock_interrupt:
            node = _make_gate_node("design", registry, settings, bus)
            result = await node({
                "project_id": "p1",
                "quality_gate_results": {},
                "started_at": "",
                "handoffs": {},
            })

        mock_interrupt.assert_called_once()
        assert "approval_requests" in result

    @pytest.mark.asyncio
    async def test_gate_without_bus(self) -> None:
        from colette.config import Settings
        from colette.gates.base import GateRegistry

        mock_result = MagicMock()
        mock_result.passed = True
        mock_result.score = 0.9
        mock_result.failure_reasons = []
        mock_result.model_dump.return_value = {"passed": True, "score": 0.9}

        registry = MagicMock(spec=GateRegistry)
        settings = Settings()

        with patch(
            "colette.orchestrator.pipeline.evaluate_gate",
            return_value=mock_result,
        ), patch(
            "colette.orchestrator.pipeline.determine_approval_action",
            return_value="auto_approve",
        ):
            node = _make_gate_node("testing", registry, settings, None)
            result = await node({
                "project_id": "p1",
                "quality_gate_results": {},
                "started_at": "",
            })

        assert result["quality_gate_results"]["testing"]["passed"] is True

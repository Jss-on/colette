"""Tests for the Monitoring stage (Phase 6)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from colette.schemas.common import GeneratedFile, StageName
from colette.schemas.deployment import DeploymentToMonitoringHandoff
from colette.stages.monitoring.incident_response import AlertRule, IncidentResponseResult
from colette.stages.monitoring.observability_agent import ObservabilityResult, SLODefinition
from colette.stages.monitoring.stage import run_stage
from colette.stages.monitoring.supervisor import (
    _deployment_to_context,
    _evaluate_quality,
    assemble_result,
    supervise_monitoring,
)

# ── Fixtures ────────────────────────────────────────────────────────────


def _make_deployment_handoff() -> DeploymentToMonitoringHandoff:
    return DeploymentToMonitoringHandoff(
        project_id="proj-1",
        deployment_id="deploy-proj-1-20260330",
        targets=[
            {
                "environment": "staging",
                "url": "https://staging.example.com",
                "health_check_url": "https://staging.example.com/health",
                "replicas": 1,
            },
        ],
        docker_images=["app:latest"],
        slo_targets={"availability": "99.9%", "p99_latency": "500ms"},
        git_ref="main",
        rollback_command="kubectl rollout undo",
        quality_gate_passed=True,
    )


def _make_obs_result() -> ObservabilityResult:
    return ObservabilityResult(
        logging_configs=[
            GeneratedFile(
                path="logging.json",
                content="{}",
                language="json",
                description="JSON logging",
            ),
        ],
        prometheus_configs=[
            GeneratedFile(
                path="prometheus.yml",
                content="scrape_configs: []",
                language="yaml",
                description="Prometheus",
            ),
        ],
        grafana_dashboards=[
            GeneratedFile(
                path="dashboard.json",
                content="{}",
                language="json",
                description="Grafana",
            ),
        ],
        health_endpoints=[
            GeneratedFile(
                path="health.py",
                content="async def health(): ...",
                language="python",
                description="Health checks",
            ),
        ],
        slo_definitions=[
            SLODefinition(
                name="availability",
                target="99.9%",
                metric="uptime",
                window="30d",
            ),
        ],
    )


def _make_incident_result() -> IncidentResponseResult:
    return IncidentResponseResult(
        alert_rules=[
            GeneratedFile(
                path="alerts.yml",
                content="groups: []",
                language="yaml",
                description="Alert rules",
            ),
        ],
        runbooks=[
            GeneratedFile(
                path="runbook.md",
                content="# Runbook",
                language="markdown",
                description="High error rate",
            ),
        ],
        incident_procedures=[
            GeneratedFile(
                path="incident.md",
                content="# RCA Template",
                language="markdown",
                description="RCA template",
            ),
        ],
        alert_rule_definitions=[
            AlertRule(
                name="error_spike",
                condition="error_rate > 5%",
                threshold="5%",
                duration="5m",
                severity="critical",
                action="page_oncall",
            ),
        ],
    )


# ── _deployment_to_context ──────────────────────────────────────────────


class TestDeploymentToContext:
    def test_includes_deployment_id(self) -> None:
        ctx = _deployment_to_context(_make_deployment_handoff())
        assert "deploy-proj-1-20260330" in ctx

    def test_includes_slo_targets(self) -> None:
        ctx = _deployment_to_context(_make_deployment_handoff())
        assert "99.9%" in ctx
        assert "500ms" in ctx

    def test_includes_docker_images(self) -> None:
        ctx = _deployment_to_context(_make_deployment_handoff())
        assert "app:latest" in ctx

    def test_includes_rollback_command(self) -> None:
        ctx = _deployment_to_context(_make_deployment_handoff())
        assert "kubectl rollout undo" in ctx


# ── _evaluate_quality ───────────────────────────────────────────────────


class TestEvaluateQuality:
    def test_passes_with_complete_results(self) -> None:
        assert _evaluate_quality(_make_obs_result(), _make_incident_result()) is True

    def test_fails_no_logging_configs(self) -> None:
        obs = ObservabilityResult(
            logging_configs=[],
            grafana_dashboards=[
                GeneratedFile(path="d.json", content="{}", language="json"),
            ],
            health_endpoints=[
                GeneratedFile(path="h.py", content="...", language="python"),
            ],
        )
        assert _evaluate_quality(obs, _make_incident_result()) is False

    def test_fails_no_grafana_dashboards(self) -> None:
        obs = ObservabilityResult(
            logging_configs=[
                GeneratedFile(path="l.json", content="{}", language="json"),
            ],
            grafana_dashboards=[],
            health_endpoints=[
                GeneratedFile(path="h.py", content="...", language="python"),
            ],
        )
        assert _evaluate_quality(obs, _make_incident_result()) is False

    def test_fails_no_alert_rules(self) -> None:
        incident = IncidentResponseResult(
            alert_rules=[],
            runbooks=[
                GeneratedFile(path="r.md", content="...", language="markdown"),
            ],
        )
        assert _evaluate_quality(_make_obs_result(), incident) is False

    def test_fails_no_health_endpoints(self) -> None:
        obs = ObservabilityResult(
            logging_configs=[
                GeneratedFile(path="l.json", content="{}", language="json"),
            ],
            grafana_dashboards=[
                GeneratedFile(path="d.json", content="{}", language="json"),
            ],
            health_endpoints=[],
        )
        assert _evaluate_quality(obs, _make_incident_result()) is False


# ── assemble_result ─────────────────────────────────────────────────────


class TestAssembleResult:
    def test_combines_all_files(self) -> None:
        result = assemble_result(
            "proj-1",
            _make_deployment_handoff(),
            _make_obs_result(),
            _make_incident_result(),
        )
        paths = [f.path for f in result.generated_files]
        # Observability files
        assert "logging.json" in paths
        assert "prometheus.yml" in paths
        assert "dashboard.json" in paths
        assert "health.py" in paths
        # Incident response files
        assert "alerts.yml" in paths
        assert "runbook.md" in paths
        assert "incident.md" in paths

    def test_includes_slo_definitions(self) -> None:
        result = assemble_result(
            "proj-1",
            _make_deployment_handoff(),
            _make_obs_result(),
            _make_incident_result(),
        )
        assert len(result.slo_definitions) == 1
        assert result.slo_definitions[0].name == "availability"
        assert result.slo_definitions[0].target == "99.9%"

    def test_includes_alert_rules(self) -> None:
        result = assemble_result(
            "proj-1",
            _make_deployment_handoff(),
            _make_obs_result(),
            _make_incident_result(),
        )
        assert len(result.alert_rules) == 1
        assert result.alert_rules[0].name == "error_spike"
        assert result.alert_rules[0].severity == "critical"

    def test_gate_passed_when_complete(self) -> None:
        result = assemble_result(
            "proj-1",
            _make_deployment_handoff(),
            _make_obs_result(),
            _make_incident_result(),
        )
        assert result.quality_gate_passed is True


# ── supervise_monitoring ────────────────────────────────────────────────


class TestSuperviseMonitoring:
    @pytest.mark.asyncio
    async def test_produces_result(self, settings: object) -> None:
        deployment = _make_deployment_handoff()

        with (
            patch(
                "colette.stages.monitoring.supervisor.run_observability_agent",
                new_callable=AsyncMock,
                return_value=_make_obs_result(),
            ),
            patch(
                "colette.stages.monitoring.supervisor.run_incident_response",
                new_callable=AsyncMock,
                return_value=_make_incident_result(),
            ),
        ):
            result = await supervise_monitoring(
                "proj-1",
                deployment,
                settings=settings,  # type: ignore[arg-type]
            )

        assert result.deployment_id == "deploy-proj-1-20260330"
        assert result.quality_gate_passed is True
        assert len(result.generated_files) == 7
        assert len(result.slo_definitions) == 1
        assert len(result.alert_rules) == 1

    @pytest.mark.asyncio
    async def test_both_agents_required(self, settings: object) -> None:
        deployment = _make_deployment_handoff()

        with (
            patch(
                "colette.stages.monitoring.supervisor.run_observability_agent",
                new_callable=AsyncMock,
                side_effect=RuntimeError("Observability agent failed"),
            ),
            patch(
                "colette.stages.monitoring.supervisor.run_incident_response",
                new_callable=AsyncMock,
                return_value=_make_incident_result(),
            ),
            pytest.raises(RuntimeError, match="Observability agent failed"),
        ):
            await supervise_monitoring(
                "proj-1",
                deployment,
                settings=settings,  # type: ignore[arg-type]
            )


# ── run_stage ───────────────────────────────────────────────────────────


class TestRunStage:
    @pytest.mark.asyncio
    async def test_raises_on_missing_deployment_handoff(self) -> None:
        state = {
            "project_id": "test-proj",
            "stage_statuses": {},
            "handoffs": {},
        }
        with pytest.raises(ValueError, match="requires a completed Deployment handoff"):
            await run_stage(state)

    @pytest.mark.asyncio
    async def test_produces_valid_state_update(self) -> None:
        deployment = _make_deployment_handoff()
        state = {
            "project_id": "test-proj",
            "stage_statuses": {},
            "handoffs": {
                StageName.DEPLOYMENT.value: deployment.to_dict(),
            },
        }

        with (
            patch(
                "colette.stages.monitoring.supervisor.run_observability_agent",
                new_callable=AsyncMock,
                return_value=_make_obs_result(),
            ),
            patch(
                "colette.stages.monitoring.supervisor.run_incident_response",
                new_callable=AsyncMock,
                return_value=_make_incident_result(),
            ),
            patch("colette.stages.monitoring.stage.Settings"),
        ):
            result = await run_stage(state)

        assert result["current_stage"] == "monitoring"
        assert result["stage_statuses"]["monitoring"] == "completed"
        assert "monitoring" in result["handoffs"]
        assert "completed_at" in result
        assert len(result["progress_events"]) == 1

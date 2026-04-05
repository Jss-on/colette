"""LangGraph pipeline connecting 6 SDLC stages with quality gates (FR-ORC-001)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import structlog
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from colette.config import Settings
from colette.gates.base import GateRegistry, evaluate_gate
from colette.human.approval import create_approval_request, determine_approval_action
from colette.orchestrator.event_bus import (
    EventType,
    PipelineEvent,
    PipelineEventBus,
    compute_elapsed,
    event_bus_var,
    project_id_var,
    stage_var,
)
from colette.orchestrator.rework_router import ReworkRouter
from colette.orchestrator.state import STAGE_ORDER, PipelineState
from colette.schemas.common import ApprovalTier, StageName, StageStatus
from colette.stages.deployment.stage import run_stage as deployment_run
from colette.stages.design.stage import run_stage as design_run
from colette.stages.implementation.stage import run_stage as implementation_run
from colette.stages.monitoring.stage import run_stage as monitoring_run
from colette.stages.requirements.stage import run_stage as requirements_run
from colette.stages.testing.stage import run_stage as testing_run

logger = structlog.get_logger()

# Mapping from stage name to its async run function.
_STAGE_RUNNERS: dict[str, Any] = {
    StageName.REQUIREMENTS.value: requirements_run,
    StageName.DESIGN.value: design_run,
    StageName.IMPLEMENTATION.value: implementation_run,
    StageName.TESTING.value: testing_run,
    StageName.DEPLOYMENT.value: deployment_run,
    StageName.MONITORING.value: monitoring_run,
}

# Each gate sits between its source stage and the next stage.
_GATE_AFTER_STAGE: dict[str, str] = {
    StageName.REQUIREMENTS.value: "requirements",
    StageName.DESIGN.value: "design",
    StageName.IMPLEMENTATION.value: "implementation",
    StageName.TESTING.value: "testing",
    StageName.DEPLOYMENT.value: "staging",
    # Monitoring is the terminus — no outgoing gate.
}


# Which approval tier each gate requires before proceeding.
# T1_HIGH always interrupts for human review at every stage.
_GATE_APPROVAL_TIER: dict[str, ApprovalTier] = {
    "requirements": ApprovalTier.T1_HIGH,
    "design": ApprovalTier.T1_HIGH,
    "implementation": ApprovalTier.T1_HIGH,
    "testing": ApprovalTier.T1_HIGH,
    "staging": ApprovalTier.T1_HIGH,
}


def _next_stage(current: str, skip_stages: list[str]) -> str | None:
    """Return the next non-skipped stage, or ``None`` if *current* is last."""
    idx = STAGE_ORDER.index(current)
    for candidate in STAGE_ORDER[idx + 1 :]:
        if candidate not in skip_stages:
            return candidate
    return None


def _summarize_handoff_for_review(gate_name: str, state: dict[str, Any]) -> dict[str, Any]:
    """Extract a comprehensive deliverable summary from the stage handoff.

    Returns all relevant handoff fields so the human reviewer gets full
    documentation for each stage before approving.
    """
    gate_to_stage = {
        "requirements": "requirements",
        "design": "design",
        "implementation": "implementation",
        "testing": "testing",
        "staging": "deployment",
    }
    stage = gate_to_stage.get(gate_name, gate_name)
    handoff = state.get("handoffs", {}).get(stage, {})
    if not handoff:
        return {"stage": stage, "note": "No handoff data available."}

    summary: dict[str, Any] = {"stage": stage}

    if stage == "requirements":
        summary["project_overview"] = handoff.get("project_overview", "")
        summary["user_stories"] = handoff.get("functional_requirements", [])
        summary["nfrs"] = handoff.get("nonfunctional_requirements", [])
        summary["tech_constraints"] = handoff.get("tech_constraints", [])
        summary["assumptions"] = handoff.get("assumptions", [])
        summary["out_of_scope"] = handoff.get("out_of_scope", [])
        summary["completeness_score"] = handoff.get("completeness_score", 0)
        summary["open_questions"] = handoff.get("open_questions", [])

    elif stage == "design":
        summary["architecture_summary"] = handoff.get("architecture_summary", "")
        summary["tech_stack"] = handoff.get("tech_stack", {})
        summary["openapi_spec"] = handoff.get("openapi_spec", "")
        summary["endpoints"] = handoff.get("endpoints", [])
        summary["db_entities"] = handoff.get("db_entities", [])
        summary["migration_strategy"] = handoff.get("migration_strategy", "")
        summary["ui_components"] = handoff.get("ui_components", [])
        summary["navigation_flows"] = handoff.get("navigation_flows", [])
        summary["adrs"] = handoff.get("adrs", [])
        summary["security_design"] = handoff.get("security_design", "")
        summary["tasks"] = handoff.get("tasks", [])

    elif stage == "implementation":
        files = handoff.get("files_changed", handoff.get("files", []))
        summary["files"] = files[:50]
        summary["file_count"] = len(files)
        summary["implemented_endpoints"] = handoff.get("implemented_endpoints", [])
        summary["packages"] = handoff.get("packages", [])
        summary["env_vars"] = handoff.get("env_vars", [])
        summary["lint_passed"] = handoff.get("lint_passed", False)
        summary["type_check_passed"] = handoff.get("type_check_passed", False)
        summary["build_passed"] = handoff.get("build_passed", False)
        summary["test_hints"] = handoff.get("test_hints", [])
        summary["git_ref"] = handoff.get("git_ref", "")

    elif stage == "testing":
        summary["test_results"] = handoff.get("test_results", [])[:30]
        summary["overall_line_coverage"] = handoff.get("overall_line_coverage", 0)
        summary["overall_branch_coverage"] = handoff.get("overall_branch_coverage", 0)
        summary["security_findings"] = handoff.get("security_findings", [])[:20]
        summary["dependency_vulnerabilities"] = handoff.get("dependency_vulnerabilities", [])[:10]
        summary["contract_tests_passed"] = handoff.get("contract_tests_passed", False)
        summary["contract_deviations"] = handoff.get("contract_deviations", [])
        summary["deploy_readiness_score"] = handoff.get("deploy_readiness_score", 0)
        summary["blocking_issues"] = handoff.get("blocking_issues", [])

    elif stage == "deployment":
        summary["deployment_id"] = handoff.get("deployment_id", "")
        summary["targets"] = handoff.get("targets", [])
        summary["docker_images"] = handoff.get("docker_images", [])
        summary["ci_pipeline_url"] = handoff.get("ci_pipeline_url", "")
        summary["rollback_command"] = handoff.get("rollback_command", "")
        summary["slo_targets"] = handoff.get("slo_targets", {})
        summary["deployment_configs"] = handoff.get("deployment_configs", [])[:10]

    # ── Attach generated file contents from state metadata ───────────
    generated = state.get("metadata", {}).get("generated_files", {}).get(stage, [])
    if generated:
        summary["generated_files"] = generated

    return summary


def _make_gate_node(
    gate_name: str,
    gate_registry: GateRegistry,
    settings: Settings,
    event_bus: PipelineEventBus | None = None,
    rework_router: ReworkRouter | None = None,
) -> Any:
    """Create an async gate-evaluation node function.

    After evaluating the gate, checks the approval tier for this gate.
    If human review is required (T0/T1, or T2 below confidence threshold),
    the node emits an approval-required event and calls ``interrupt()``
    to pause the pipeline until the user approves via ``colette approve``.
    """

    async def _gate_node(state: dict[str, Any]) -> dict[str, Any]:
        project_id = state.get("project_id", "")
        gate = gate_registry.get(gate_name)
        result = await evaluate_gate(gate, state)

        if event_bus is not None:
            event_type = EventType.GATE_PASSED if result.passed else EventType.GATE_FAILED
            event_bus.emit(
                PipelineEvent(
                    project_id=project_id,
                    event_type=event_type,
                    stage=gate_name,
                    message="" if result.passed else "; ".join(result.failure_reasons),
                    detail=result.model_dump(mode="json"),
                    elapsed_seconds=compute_elapsed(state.get("started_at", "")),
                )
            )

        gate_state: dict[str, Any] = {
            "quality_gate_results": {
                **state.get("quality_gate_results", {}),
                gate_name: result.model_dump(mode="json"),
            },
            "progress_events": [
                {
                    "type": "gate_evaluated",
                    "gate": gate_name,
                    "passed": result.passed,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            ],
        }

        # ── Rework routing (Phase 1) ──────────────────────────────
        if not result.passed and rework_router is not None:
            rework_count = dict(state.get("rework_count", {}))
            decision, directive = rework_router.decide(result, rework_count)

            if directive is not None:
                # Increment rework count for target stage.
                target = directive.target_stage
                rework_count[target] = rework_count.get(target, 0) + 1
                gate_state["rework_count"] = rework_count
                gate_state["current_rework"] = directive.model_dump(mode="json")
                gate_state["rework_directives"] = [directive.model_dump(mode="json")]

                if event_bus is not None:
                    event_bus.emit(
                        PipelineEvent(
                            project_id=project_id,
                            event_type=EventType.GATE_FAILED,
                            stage=gate_name,
                            message=(
                                f"Rework triggered: {decision.value} -> "
                                f"{target} (attempt {directive.attempt_number})"
                            ),
                            detail=directive.model_dump(mode="json"),
                            elapsed_seconds=compute_elapsed(state.get("started_at", "")),
                        )
                    )

                # Store decision on the result so the router function can read it.
                gate_state["quality_gate_results"] = {
                    **state.get("quality_gate_results", {}),
                    gate_name: {
                        **result.model_dump(mode="json"),
                        "rework_decision": decision.value,
                        "rework_target_stage": target,
                    },
                }

        # ── Human-in-the-loop check (FR-HIL-001) ────────────────────
        if result.passed:
            tier = _GATE_APPROVAL_TIER.get(gate_name, ApprovalTier.T3_ROUTINE)
            action = determine_approval_action(tier, result.score, settings)
            if action == "interrupt":
                approval_req = create_approval_request(
                    state,
                    tier,
                    context_summary=(
                        f"Gate '{gate_name}' passed with score "
                        f"{result.score:.2f}. "
                        f"Criteria: {result.criteria_results}"
                    ),
                    proposed_action=f"Proceed to next stage after {gate_name}",
                    confidence=result.score,
                    settings=settings,
                )
                gate_state["approval_requests"] = [approval_req.model_dump(mode="json")]

                if event_bus is not None:
                    handoff_summary = _summarize_handoff_for_review(gate_name, state)
                    event_detail = {
                        **approval_req.model_dump(mode="json"),
                        "handoff_summary": handoff_summary,
                    }
                    event_bus.emit(
                        PipelineEvent(
                            project_id=project_id,
                            event_type=EventType.APPROVAL_REQUIRED,
                            stage=gate_name,
                            message=(
                                f"Human approval required ({tier}). "
                                f"Run: colette approve {approval_req.request_id}"
                            ),
                            detail=event_detail,
                            elapsed_seconds=compute_elapsed(state.get("started_at", "")),
                        )
                    )

                logger.info(
                    "gate.approval_required",
                    gate=gate_name,
                    tier=tier,
                    request_id=approval_req.request_id,
                )
                # Pause pipeline — resumed via `colette approve`
                interrupt(approval_req.model_dump(mode="json"))

        return gate_state

    _gate_node.__name__ = f"gate_{gate_name}"
    return _gate_node


def _make_stage_node(stage_name: str, event_bus: PipelineEventBus | None = None) -> Any:
    """Wrap a stage runner to mark the stage as RUNNING before execution."""
    runner = _STAGE_RUNNERS[stage_name]

    async def _stage_node(state: dict[str, Any]) -> dict[str, Any]:
        project_id = state.get("project_id", "")

        # ── Rework context (Phase 1) ──────────────────────────────
        current_rework = state.get("current_rework")
        if current_rework:
            logger.info(
                "stage.rework_context",
                stage=stage_name,
                source_gate=current_rework.get("source_gate"),
                attempt=current_rework.get("attempt_number"),
                reasons=current_rework.get("failure_reasons", []),
            )

        if event_bus is not None:
            event_bus.emit(
                PipelineEvent(
                    project_id=project_id,
                    event_type=EventType.STAGE_STARTED,
                    stage=stage_name,
                    elapsed_seconds=compute_elapsed(state.get("started_at", "")),
                )
            )

        # Mark running
        updated_statuses = {
            **state.get("stage_statuses", {}),
            stage_name: StageStatus.RUNNING.value,
        }
        running_state = {**state, "stage_statuses": updated_statuses}

        # Set context vars so callbacks can emit agent-level events.
        t1 = event_bus_var.set(event_bus)
        t2 = project_id_var.set(project_id)
        t3 = stage_var.set(stage_name)
        try:
            result: dict[str, Any] = await runner(running_state)
        except Exception as exc:
            if event_bus is not None:
                event_bus.emit(
                    PipelineEvent(
                        project_id=project_id,
                        event_type=EventType.STAGE_FAILED,
                        stage=stage_name,
                        message=str(exc),
                        elapsed_seconds=compute_elapsed(state.get("started_at", "")),
                    )
                )
            raise
        finally:
            event_bus_var.reset(t1)
            project_id_var.reset(t2)
            stage_var.reset(t3)

        if event_bus is not None:
            event_bus.emit(
                PipelineEvent(
                    project_id=project_id,
                    event_type=EventType.STAGE_COMPLETED,
                    stage=stage_name,
                    elapsed_seconds=compute_elapsed(state.get("started_at", "")),
                )
            )

        # Clear rework context after the stage has processed it.
        if current_rework:
            result["current_rework"] = None

        return result

    _stage_node.__name__ = f"stage_{stage_name}"
    return _stage_node


def _gate_router(gate_name: str, source_stage: str, skip_stages: list[str]) -> Any:
    """Create a routing function for post-gate conditional edges.

    Supports rework routing: when a gate fails with a rework decision,
    routes to the target stage (creating a backward edge) instead of
    the ``gate_failed`` terminal.
    """

    def _router(state: dict[str, Any]) -> str:
        result = state.get("quality_gate_results", {}).get(gate_name, {})
        if result.get("passed", False):
            nxt = _next_stage(source_stage, state.get("skip_stages", skip_stages))
            if nxt is None:
                return "end"
            return f"stage_{nxt}"

        # Check for rework decision.
        rework_decision = result.get("rework_decision", "pass")
        if rework_decision in ("rework_self", "rework_target"):
            target = result.get("rework_target_stage")
            if target:
                return f"stage_{target}"

        # No rework — route to error terminal.
        return "gate_failed"

    return _router


def build_pipeline(
    gate_registry: GateRegistry,
    settings: Settings,
    *,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
    event_bus: PipelineEventBus | None = None,
) -> CompiledStateGraph[Any]:
    """Build and compile the 6-stage SDLC pipeline.

    Parameters
    ----------
    gate_registry:
        Registry containing all quality gates.
    settings:
        Application settings.
    checkpointer:
        Optional LangGraph checkpoint saver for durable execution.
    event_bus:
        Optional event bus for emitting pipeline progress events.

    Returns
    -------
    CompiledStateGraph
        Ready to invoke via ``graph.ainvoke()`` or ``graph.astream()``.
    """
    rework_router = ReworkRouter(settings)
    graph = StateGraph(PipelineState)

    # ── Add stage nodes ──────────────────────────────────────────────
    for stage_name in STAGE_ORDER:
        graph.add_node(f"stage_{stage_name}", _make_stage_node(stage_name, event_bus))

    # ── Add gate nodes (after each stage except monitoring) ──────────
    for _stage_name, gate_name in _GATE_AFTER_STAGE.items():
        graph.add_node(
            f"gate_{gate_name}",
            _make_gate_node(gate_name, gate_registry, settings, event_bus, rework_router),
        )

    # ── Gate-failed terminal node ────────────────────────────────────
    async def _gate_failed(state: dict[str, Any]) -> dict[str, Any]:
        current = state.get("current_stage", "unknown")
        logger.warning("pipeline.gate_failed", stage=current)
        return {
            "stage_statuses": {
                **state.get("stage_statuses", {}),
                current: StageStatus.BLOCKED_BY_GATE.value,
            },
            "error_log": [
                {
                    "type": "gate_failure",
                    "stage": current,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            ],
        }

    graph.add_node("gate_failed", _gate_failed)  # type: ignore[type-var]

    # ── Wire edges ───────────────────────────────────────────────────
    # START -> first stage
    graph.add_edge(START, f"stage_{STAGE_ORDER[0]}")

    # stage -> gate -> conditional(next_stage | gate_failed)
    for stage_name, gate_name in _GATE_AFTER_STAGE.items():
        gate_node = f"gate_{gate_name}"
        graph.add_edge(f"stage_{stage_name}", gate_node)

        # Build possible destinations for this gate
        possible: dict[str, str] = {"gate_failed": "gate_failed", "end": END}
        nxt = _next_stage(stage_name, [])
        if nxt:
            possible[f"stage_{nxt}"] = f"stage_{nxt}"
        # Also add all possible next stages (for skip logic)
        for s in STAGE_ORDER:
            key = f"stage_{s}"
            if key not in possible:
                possible[key] = key

        graph.add_conditional_edges(
            gate_node,
            _gate_router(gate_name, stage_name, []),
            cast(dict[Any, str], possible),
        )

    # monitoring (final stage) -> END
    graph.add_edge(f"stage_{StageName.MONITORING.value}", END)

    # gate_failed -> END
    graph.add_edge("gate_failed", END)

    # Use max_super_steps to prevent infinite rework cycles.
    return graph.compile(
        checkpointer=checkpointer,
    )

"""LangGraph pipeline connecting 6 SDLC stages with quality gates (FR-ORC-001)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import structlog
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from colette.config import Settings
from colette.gates.base import GateRegistry, evaluate_gate
from colette.orchestrator.event_bus import (
    EventType,
    PipelineEvent,
    PipelineEventBus,
    compute_elapsed,
)
from colette.orchestrator.state import STAGE_ORDER, PipelineState
from colette.schemas.common import StageName, StageStatus
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


def _next_stage(current: str, skip_stages: list[str]) -> str | None:
    """Return the next non-skipped stage, or ``None`` if *current* is last."""
    idx = STAGE_ORDER.index(current)
    for candidate in STAGE_ORDER[idx + 1 :]:
        if candidate not in skip_stages:
            return candidate
    return None


def _make_gate_node(
    gate_name: str,
    gate_registry: GateRegistry,
    event_bus: PipelineEventBus | None = None,
) -> Any:
    """Create an async gate-evaluation node function."""

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

        return {
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

    _gate_node.__name__ = f"gate_{gate_name}"
    return _gate_node


def _make_stage_node(
    stage_name: str, event_bus: PipelineEventBus | None = None
) -> Any:
    """Wrap a stage runner to mark the stage as RUNNING before execution."""
    runner = _STAGE_RUNNERS[stage_name]

    async def _stage_node(state: dict[str, Any]) -> dict[str, Any]:
        project_id = state.get("project_id", "")

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

        if event_bus is not None:
            event_bus.emit(
                PipelineEvent(
                    project_id=project_id,
                    event_type=EventType.STAGE_COMPLETED,
                    stage=stage_name,
                    elapsed_seconds=compute_elapsed(state.get("started_at", "")),
                )
            )

        return result

    _stage_node.__name__ = f"stage_{stage_name}"
    return _stage_node


def _gate_router(gate_name: str, source_stage: str, skip_stages: list[str]) -> Any:
    """Create a routing function for post-gate conditional edges."""

    def _router(state: dict[str, Any]) -> str:
        result = state.get("quality_gate_results", {}).get(gate_name, {})
        if result.get("passed", False):
            nxt = _next_stage(source_stage, state.get("skip_stages", skip_stages))
            if nxt is None:
                return "end"
            return f"stage_{nxt}"
        # Gate failed — route to error terminal
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
    graph = StateGraph(PipelineState)

    # ── Add stage nodes ──────────────────────────────────────────────
    for stage_name in STAGE_ORDER:
        graph.add_node(f"stage_{stage_name}", _make_stage_node(stage_name, event_bus))

    # ── Add gate nodes (after each stage except monitoring) ──────────
    for _stage_name, gate_name in _GATE_AFTER_STAGE.items():
        graph.add_node(
            f"gate_{gate_name}",
            _make_gate_node(gate_name, gate_registry, event_bus),
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

    return graph.compile(checkpointer=checkpointer)

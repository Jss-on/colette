"""Quality gate protocol and registry (Section 12)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

import structlog

from colette.schemas.common import QualityGateResult

logger = structlog.get_logger()


@runtime_checkable
class QualityGate(Protocol):
    """Protocol that all quality gates must implement."""

    @property
    def name(self) -> str: ...

    async def evaluate(self, state: dict[str, Any]) -> QualityGateResult: ...


class GateRegistry:
    """Maps gate names to ``QualityGate`` instances."""

    def __init__(self) -> None:
        self._gates: dict[str, QualityGate] = {}

    def register(self, gate: QualityGate) -> None:
        self._gates[gate.name] = gate

    def get(self, name: str) -> QualityGate:
        if name not in self._gates:
            msg = f"No gate registered with name '{name}'"
            raise KeyError(msg)
        return self._gates[name]

    def all_gates(self) -> dict[str, QualityGate]:
        return dict(self._gates)


async def evaluate_gate(gate: QualityGate, state: dict[str, Any]) -> QualityGateResult:
    """Evaluate a gate with error handling — never raises, always returns a result."""
    try:
        result = await gate.evaluate(state)
        logger.info(
            "gate.evaluated",
            gate=gate.name,
            passed=result.passed,
            score=result.score,
        )
        return result
    except Exception as exc:
        logger.error("gate.error", gate=gate.name, error=str(exc))
        return QualityGateResult(
            gate_name=gate.name,
            passed=False,
            score=0.0,
            failure_reasons=[f"Gate evaluation error: {exc}"],
            evaluated_at=datetime.now(UTC),
        )

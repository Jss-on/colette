"""Tests for gate protocol, registry, and evaluate_gate helper."""

from __future__ import annotations

from typing import Any

import pytest

from colette.gates.base import GateRegistry, QualityGate, evaluate_gate
from colette.schemas.common import QualityGateResult


class _PassingGate:
    @property
    def name(self) -> str:
        return "passing"

    async def evaluate(self, state: dict[str, Any]) -> QualityGateResult:
        return QualityGateResult(gate_name=self.name, passed=True, score=1.0)


class _FailingGate:
    @property
    def name(self) -> str:
        return "failing"

    async def evaluate(self, state: dict[str, Any]) -> QualityGateResult:
        return QualityGateResult(
            gate_name=self.name,
            passed=False,
            score=0.3,
            failure_reasons=["Test failure"],
        )


class _CrashingGate:
    @property
    def name(self) -> str:
        return "crashing"

    async def evaluate(self, state: dict[str, Any]) -> QualityGateResult:
        msg = "boom"
        raise RuntimeError(msg)


class TestGateRegistry:
    def test_register_and_get(self) -> None:
        reg = GateRegistry()
        gate = _PassingGate()
        reg.register(gate)
        assert reg.get("passing") is gate

    def test_get_missing_raises(self) -> None:
        reg = GateRegistry()
        with pytest.raises(KeyError, match="no_such"):
            reg.get("no_such")

    def test_all_gates(self) -> None:
        reg = GateRegistry()
        reg.register(_PassingGate())
        reg.register(_FailingGate())
        assert len(reg.all_gates()) == 2


class TestEvaluateGate:
    @pytest.mark.asyncio
    async def test_passing_gate(self) -> None:
        result = await evaluate_gate(_PassingGate(), {})
        assert result.passed is True
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_failing_gate(self) -> None:
        result = await evaluate_gate(_FailingGate(), {})
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_crashing_gate_returns_failed_result(self) -> None:
        result = await evaluate_gate(_CrashingGate(), {})
        assert result.passed is False
        assert "boom" in result.failure_reasons[0]


class TestQualityGateProtocol:
    def test_passing_gate_implements_protocol(self) -> None:
        assert isinstance(_PassingGate(), QualityGate)

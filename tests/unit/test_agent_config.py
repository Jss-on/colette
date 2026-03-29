"""Tests for AgentConfig model (FR-ORC-010/017, FR-MEM-004)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from colette.schemas.agent_config import (
    MAX_TOOLS_PER_AGENT,
    SPECIALIST_BUDGET,
    SUPERVISOR_BUDGET,
    VALIDATOR_BUDGET,
    AgentConfig,
    AgentRole,
    ContextBudgetAllocation,
    ModelTier,
)
from colette.schemas.common import ApprovalTier


class TestAgentConfig:
    def _make(self, **overrides: object) -> AgentConfig:
        defaults: dict[str, object] = {
            "role": AgentRole.BACKEND_DEV,
            "system_prompt": "You are a backend developer.",
        }
        defaults.update(overrides)
        return AgentConfig(**defaults)  # type: ignore[arg-type]

    def test_defaults(self) -> None:
        cfg = self._make()
        assert cfg.model_tier == ModelTier.EXECUTION
        assert cfg.max_iterations == 25
        assert cfg.timeout_seconds == 600
        assert cfg.context_budget_tokens == 60_000
        assert cfg.approval_tier == ApprovalTier.T3_ROUTINE

    def test_tool_count_within_limit(self) -> None:
        cfg = self._make(tool_names=["read", "write", "search"])
        assert len(cfg.tool_names) == 3

    def test_tool_count_at_limit(self) -> None:
        cfg = self._make(tool_names=["a", "b", "c", "d", "e"])
        assert len(cfg.tool_names) == MAX_TOOLS_PER_AGENT

    def test_tool_count_exceeds_limit(self) -> None:
        """FR-ORC-017: more than 5 tools must be rejected."""
        with pytest.raises(ValidationError, match="at most 5"):
            self._make(tool_names=["a", "b", "c", "d", "e", "f"])

    def test_empty_system_prompt_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._make(system_prompt="")

    def test_model_name_override(self) -> None:
        cfg = self._make(model_name="gpt-5.4")
        assert cfg.model_name == "gpt-5.4"

    def test_all_agent_roles_valid(self) -> None:
        for role in AgentRole:
            cfg = self._make(role=role)
            assert cfg.role == role


class TestContextBudgetAllocation:
    def test_default_sums_to_one(self) -> None:
        b = ContextBudgetAllocation()
        total = b.system_prompt + b.tools + b.retrieved_context + b.history + b.output
        assert abs(total - 1.0) < 0.01

    def test_supervisor_budget(self) -> None:
        assert SUPERVISOR_BUDGET.output == 0.25

    def test_specialist_budget(self) -> None:
        assert SPECIALIST_BUDGET.retrieved_context == 0.40

    def test_validator_budget(self) -> None:
        assert VALIDATOR_BUDGET.system_prompt == 0.15

    def test_invalid_allocation_raises(self) -> None:
        with pytest.raises(ValueError, match=r"sum to 1\.0"):
            ContextBudgetAllocation(
                system_prompt=0.50,
                tools=0.50,
                retrieved_context=0.50,
                history=0.50,
                output=0.50,
            )

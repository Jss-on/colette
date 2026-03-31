"""Tests for application configuration."""

import os

from colette.config import Settings


def test_default_settings() -> None:
    s = Settings()
    assert s.agent_max_iterations == 25
    assert s.supervisor_context_budget == 100_000
    assert s.specialist_context_budget == 60_000
    assert s.validator_context_budget == 30_000


def test_settings_override(monkeypatch: object) -> None:
    os.environ["COLETTE_AGENT_MAX_ITERATIONS"] = "50"
    try:
        s = Settings()
        assert s.agent_max_iterations == 50
    finally:
        del os.environ["COLETTE_AGENT_MAX_ITERATIONS"]


def test_llm_fallback_defaults_empty() -> None:
    s = Settings()
    assert s.planning_fallback_models == []
    assert s.execution_fallback_models == []
    assert s.validation_fallback_models == []


def test_llm_model_defaults() -> None:
    s = Settings()
    assert "claude" in s.default_planning_model
    assert "claude" in s.default_execution_model
    assert "claude" in s.default_validation_model


def test_handoff_max_chars_default() -> None:
    s = Settings()
    assert s.handoff_max_chars == 32_000

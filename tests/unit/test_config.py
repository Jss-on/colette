"""Tests for application configuration."""

from colette.config import Settings


def test_default_settings() -> None:
    s = Settings()
    assert s.agent_max_iterations == 25
    assert s.supervisor_context_budget == 100_000
    assert s.specialist_context_budget == 60_000
    assert s.validator_context_budget == 30_000


def test_settings_override(monkeypatch: object) -> None:
    import os

    os.environ["COLETTE_AGENT_MAX_ITERATIONS"] = "50"
    try:
        s = Settings()
        assert s.agent_max_iterations == 50
    finally:
        del os.environ["COLETTE_AGENT_MAX_ITERATIONS"]

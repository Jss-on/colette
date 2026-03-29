"""Tests for LLM gateway, model registry, and token counter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from colette.config import Settings
from colette.llm.models import ModelChain, ModelRegistry
from colette.llm.token_counter import check_budget, estimate_tokens, estimate_tokens_for_messages
from colette.schemas.agent_config import AgentConfig, AgentRole, ModelTier

# ── Token counter ────────────────────────────────────────────────────


class TestTokenCounter:
    def test_estimate_tokens_basic(self) -> None:
        assert estimate_tokens("hello world") >= 1

    def test_estimate_tokens_empty(self) -> None:
        assert estimate_tokens("") == 1  # minimum 1

    def test_estimate_tokens_longer(self) -> None:
        text = "a" * 400  # ~100 tokens
        tokens = estimate_tokens(text)
        assert 90 <= tokens <= 110

    def test_estimate_tokens_for_messages(self) -> None:
        msgs = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello!"},
        ]
        tokens = estimate_tokens_for_messages(msgs)
        assert tokens > 0

    def test_check_budget_within(self) -> None:
        within, needs_compact = check_budget(30_000, 60_000)
        assert within is True
        assert needs_compact is False

    def test_check_budget_needs_compaction(self) -> None:
        within, needs_compact = check_budget(45_000, 60_000)  # 75% > 70%
        assert within is True
        assert needs_compact is True

    def test_check_budget_exceeded(self) -> None:
        within, needs_compact = check_budget(65_000, 60_000)
        assert within is False
        assert needs_compact is True


# ── Model registry ───────────────────────────────────────────────────


class TestModelRegistry:
    def test_default_registry(self) -> None:
        reg = ModelRegistry()
        assert "opus" in reg.planning.primary
        assert "sonnet" in reg.execution.primary

    def test_from_settings(self) -> None:
        settings = Settings()
        reg = ModelRegistry.from_settings(settings)
        assert reg.planning.primary == settings.default_planning_model
        assert len(reg.planning.fallbacks) == len(settings.planning_fallback_models)

    def test_get_chain_planning(self) -> None:
        reg = ModelRegistry()
        chain = reg.get_chain(ModelTier.PLANNING)
        assert chain is reg.planning

    def test_get_chain_execution(self) -> None:
        reg = ModelRegistry()
        chain = reg.get_chain(ModelTier.EXECUTION)
        assert chain is reg.execution

    def test_get_chain_validation(self) -> None:
        reg = ModelRegistry()
        chain = reg.get_chain(ModelTier.VALIDATION)
        assert chain is reg.validation

    def test_model_chain_immutable(self) -> None:
        chain = ModelChain(primary="test", fallbacks=("a", "b"))
        assert chain.primary == "test"
        assert chain.fallbacks == ("a", "b")


# ── Gateway factory ──────────────────────────────────────────────────


class TestGatewayFactory:
    def _make_config(self, **overrides: object) -> AgentConfig:
        defaults: dict[str, object] = {
            "role": AgentRole.BACKEND_DEV,
            "system_prompt": "You are a backend developer.",
            "model_tier": ModelTier.EXECUTION,
        }
        defaults.update(overrides)
        return AgentConfig(**defaults)  # type: ignore[arg-type]

    @patch("colette.llm.gateway._build_chat_model")
    def test_explicit_model_override(self, mock_build: MagicMock) -> None:
        from colette.llm.gateway import create_chat_model

        mock_build.return_value = MagicMock()
        cfg = self._make_config(model_name="custom-model")
        settings = Settings()

        create_chat_model(cfg, settings=settings)

        mock_build.assert_called_once_with(
            "custom-model",
            base_url=settings.litellm_base_url,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    @patch("colette.llm.gateway._build_chat_model")
    def test_tier_based_with_fallbacks(self, mock_build: MagicMock) -> None:
        from colette.llm.gateway import create_chat_model

        primary_mock = MagicMock()
        primary_mock.with_fallbacks.return_value = MagicMock()
        mock_build.return_value = primary_mock

        cfg = self._make_config(model_tier=ModelTier.PLANNING)
        settings = Settings()
        registry = ModelRegistry.from_settings(settings)

        create_chat_model(cfg, settings=settings, registry=registry)

        # Primary + fallbacks should be built
        expected_calls = 1 + len(settings.planning_fallback_models)
        assert mock_build.call_count == expected_calls

    @patch("colette.llm.gateway._build_chat_model")
    def test_no_fallbacks_when_chain_empty(self, mock_build: MagicMock) -> None:
        from colette.llm.gateway import create_chat_model

        mock_build.return_value = MagicMock()

        cfg = self._make_config()
        registry = ModelRegistry(
            execution=ModelChain(primary="test-model", fallbacks=()),
        )
        settings = Settings()

        result = create_chat_model(cfg, settings=settings, registry=registry)

        # No fallbacks — should just return the primary mock directly
        assert result is mock_build.return_value
        mock_build.assert_called_once()

    @patch("colette.llm.gateway._build_chat_model")
    def test_create_chat_model_for_tier(self, mock_build: MagicMock) -> None:
        from colette.llm.gateway import create_chat_model_for_tier

        primary_mock = MagicMock()
        primary_mock.with_fallbacks.return_value = MagicMock()
        mock_build.return_value = primary_mock

        settings = Settings()
        create_chat_model_for_tier(ModelTier.EXECUTION, settings=settings)

        assert mock_build.call_count >= 1

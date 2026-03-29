"""LLM gateway factory: ChatModel with fallback chains (FR-TL-006, FR-ORC-014).

All LLM access in Colette goes through `create_chat_model()`.  This ensures:
- Provider-agnostic interface via LangChain ChatModel (DC-007)
- Automatic failover via `with_fallbacks()` (FR-ORC-014)
- Consistent configuration (timeout, retries, caching)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.language_models import BaseChatModel

from colette.llm.models import ModelChain, ModelRegistry

if TYPE_CHECKING:
    from colette.config import Settings
    from colette.schemas.agent_config import AgentConfig, ModelTier


def _build_chat_model(
    model_name: str,
    *,
    base_url: str | None = None,
    timeout: int = 120,
    max_retries: int = 2,
) -> BaseChatModel:
    """Instantiate a single ChatLiteLLM model.

    We import inside the function so the module stays importable even
    when ``langchain_community`` is not installed (e.g. during type-checking).
    """
    from langchain_community.chat_models import ChatLiteLLM

    kwargs: dict[str, object] = {
        "model": model_name,
        "max_retries": max_retries,
        "request_timeout": timeout,
    }
    if base_url:
        kwargs["api_base"] = base_url

    model: BaseChatModel = ChatLiteLLM(**kwargs)
    return model


def _build_chain_with_fallbacks(
    chain: ModelChain,
    *,
    base_url: str | None = None,
    timeout: int = 120,
    max_retries: int = 2,
) -> BaseChatModel:
    """Build a primary ChatModel with ordered fallbacks (FR-ORC-014)."""
    primary = _build_chat_model(
        chain.primary, base_url=base_url, timeout=timeout, max_retries=max_retries
    )
    if not chain.fallbacks:
        return primary

    fallback_models = [
        _build_chat_model(name, base_url=base_url, timeout=timeout, max_retries=max_retries)
        for name in chain.fallbacks
    ]
    return primary.with_fallbacks(fallback_models)  # type: ignore[return-value]


def create_chat_model(
    agent_config: AgentConfig,
    *,
    settings: Settings | None = None,
    registry: ModelRegistry | None = None,
) -> BaseChatModel:
    """Create a ChatModel for the given agent configuration.

    Resolution order for the model name:
    1. ``agent_config.model_name`` (explicit override)
    2. ``registry.get_chain(agent_config.model_tier)`` (tier-based with fallbacks)

    Args:
        agent_config: The agent's configuration.
        settings: Application settings.  Loaded from env if not provided.
        registry: Model registry.  Built from settings if not provided.

    Returns:
        A LangChain BaseChatModel (possibly with fallbacks attached).
    """
    if settings is None:
        from colette.config import Settings

        settings = Settings()

    if registry is None:
        registry = ModelRegistry.from_settings(settings)

    # Explicit model override — no fallback chain.
    if agent_config.model_name:
        return _build_chat_model(
            agent_config.model_name,
            base_url=settings.litellm_base_url,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    # Tier-based resolution with fallback chain.
    chain = registry.get_chain(agent_config.model_tier)
    return _build_chain_with_fallbacks(
        chain,
        base_url=settings.litellm_base_url,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )


def create_chat_model_for_tier(
    tier: ModelTier,
    *,
    settings: Settings | None = None,
    registry: ModelRegistry | None = None,
) -> BaseChatModel:
    """Convenience: create a ChatModel by tier without a full AgentConfig."""
    if settings is None:
        from colette.config import Settings

        settings = Settings()

    if registry is None:
        registry = ModelRegistry.from_settings(settings)

    chain = registry.get_chain(tier)
    return _build_chain_with_fallbacks(
        chain,
        base_url=settings.litellm_base_url,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )

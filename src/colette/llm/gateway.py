"""LLM gateway factory: ChatModel with fallback chains (FR-TL-006, FR-ORC-014).

All LLM access in Colette goes through `create_chat_model()`.  This ensures:
- Provider-agnostic interface via LangChain ChatModel (DC-007)
- Automatic failover via `with_fallbacks()` (FR-ORC-014)
- Consistent configuration (timeout, retries, caching)
- **Project status guard** — LLM calls are blocked for non-running projects
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from pydantic import ConfigDict

from colette.llm.models import ModelChain, ModelRegistry
from colette.llm.registry import project_status_registry

if TYPE_CHECKING:
    from colette.config import Settings
    from colette.schemas.agent_config import AgentConfig, ModelTier

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Guarded wrapper — blocks LLM calls for non-running projects
# ---------------------------------------------------------------------------


class GuardedChatModel(BaseChatModel):
    """Transparent wrapper that checks project status before every LLM call.

    If the project is not ``"running"`` in the :data:`project_status_registry`,
    a :class:`~colette.llm.registry.ProjectNotActiveError` is raised
    **before** any API request is made.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    inner: BaseChatModel
    project_id: str

    @property
    def _llm_type(self) -> str:
        return f"guarded-{self.inner._llm_type}"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        project_status_registry.assert_active(self.project_id)
        return self.inner._generate(messages, stop, run_manager, **kwargs)

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        project_status_registry.assert_active(self.project_id)
        return await self.inner._agenerate(messages, stop, run_manager, **kwargs)


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

    Args:
        model_name: LiteLLM model identifier (e.g. ``"claude-sonnet-4-6-20250514"``).
        base_url: Optional LiteLLM proxy base URL.
        timeout: Request timeout in seconds.
        max_retries: Number of retries on transient failures.

    Returns:
        A configured :class:`BaseChatModel` instance.
    """
    from langchain_community.chat_models import ChatLiteLLM

    kwargs: dict[str, Any] = {
        "model": model_name,
        "max_retries": max_retries,
        "request_timeout": timeout,
    }
    if base_url:
        kwargs["api_base"] = base_url

    logger.debug("building_chat_model", model=model_name, timeout=timeout)
    model: BaseChatModel = ChatLiteLLM(**kwargs)
    return model


def _build_chain_with_fallbacks(
    chain: ModelChain,
    *,
    base_url: str | None = None,
    timeout: int = 120,
    max_retries: int = 2,
) -> BaseChatModel:
    """Build a primary ChatModel with ordered fallbacks (FR-ORC-014).

    Args:
        chain: Primary model name plus fallback alternatives.
        base_url: Optional LiteLLM proxy base URL.
        timeout: Request timeout in seconds.
        max_retries: Number of retries on transient failures.

    Returns:
        A :class:`BaseChatModel`, optionally wrapped with fallback models.
    """
    primary = _build_chat_model(
        chain.primary, base_url=base_url, timeout=timeout, max_retries=max_retries
    )
    if not chain.fallbacks:
        return primary

    logger.info(
        "configuring_fallback_chain",
        primary=chain.primary,
        fallbacks=chain.fallbacks,
    )
    fallback_models = [
        _build_chat_model(name, base_url=base_url, timeout=timeout, max_retries=max_retries)
        for name in chain.fallbacks
    ]
    return primary.with_fallbacks(fallback_models)  # type: ignore[return-value]


def _maybe_guard(model: BaseChatModel, project_id: str | None) -> BaseChatModel:
    """Wrap *model* in a :class:`GuardedChatModel` if *project_id* is given."""
    if project_id is None:
        return model
    return GuardedChatModel(inner=model, project_id=project_id)


def create_chat_model(
    agent_config: AgentConfig,
    *,
    settings: Settings | None = None,
    registry: ModelRegistry | None = None,
    project_id: str | None = None,
) -> BaseChatModel:
    """Create a ChatModel for the given agent configuration.

    Resolution order for the model name:

    1. ``agent_config.model_name`` (explicit override)
    2. ``registry.get_chain(agent_config.model_tier)`` (tier-based with fallbacks)

    When *project_id* is provided the returned model is wrapped in a
    :class:`GuardedChatModel` that checks the :data:`project_status_registry`
    before every LLM call, blocking requests for non-running projects.

    Args:
        agent_config: The agent's configuration.
        settings: Application settings.  Loaded from env if not provided.
        registry: Model registry.  Built from settings if not provided.
        project_id: If given, every LLM call checks the project is still active.

    Returns:
        A LangChain :class:`BaseChatModel` (possibly guarded and/or with fallbacks).
    """
    if settings is None:
        from colette.config import Settings

        settings = Settings()

    if registry is None:
        registry = ModelRegistry.from_settings(settings)

    # Explicit model override -- no fallback chain.
    if agent_config.model_name:
        logger.info(
            "creating_chat_model",
            role=str(agent_config.role),
            model=agent_config.model_name,
            source="explicit_override",
            guarded=project_id is not None,
        )
        model = _build_chat_model(
            agent_config.model_name,
            base_url=settings.litellm_base_url,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )
        return _maybe_guard(model, project_id)

    # Tier-based resolution with fallback chain.
    chain = registry.get_chain(agent_config.model_tier)
    logger.info(
        "creating_chat_model",
        role=str(agent_config.role),
        tier=str(agent_config.model_tier),
        primary=chain.primary,
        source="tier_registry",
        guarded=project_id is not None,
    )
    model = _build_chain_with_fallbacks(
        chain,
        base_url=settings.litellm_base_url,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )
    return _maybe_guard(model, project_id)


def create_chat_model_for_tier(
    tier: ModelTier,
    *,
    settings: Settings | None = None,
    registry: ModelRegistry | None = None,
    project_id: str | None = None,
) -> BaseChatModel:
    """Convenience: create a ChatModel by tier without a full AgentConfig.

    Args:
        tier: The model tier (planning, execution, or validation).
        settings: Application settings.  Loaded from env if not provided.
        registry: Model registry.  Built from settings if not provided.
        project_id: If given, every LLM call checks the project is still active.

    Returns:
        A LangChain :class:`BaseChatModel` with the tier's fallback chain
        (possibly wrapped in a :class:`GuardedChatModel`).
    """
    if settings is None:
        from colette.config import Settings

        settings = Settings()

    if registry is None:
        registry = ModelRegistry.from_settings(settings)

    chain = registry.get_chain(tier)
    logger.info(
        "creating_chat_model_for_tier",
        tier=str(tier),
        primary=chain.primary,
        guarded=project_id is not None,
    )
    model = _build_chain_with_fallbacks(
        chain,
        base_url=settings.litellm_base_url,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )
    return _maybe_guard(model, project_id)

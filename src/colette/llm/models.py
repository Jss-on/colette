"""Model registry mapping agent tiers to LLM model names (FR-TL-006)."""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from colette.config import Settings
from colette.schemas.agent_config import ModelTier

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ModelChain:
    """A primary model plus ordered fallback alternatives.

    Attributes:
        primary: The preferred model identifier.
        fallbacks: Ordered tuple of fallback model identifiers tried on failure.
    """

    primary: str
    fallbacks: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelRegistry:
    """Resolves agent model tiers to concrete model names from settings.

    Immutable after construction -- create a new instance if settings change.

    Attributes:
        planning: Model chain for planning-tier agents (Orchestrator, Design Supervisor).
        reasoning: Model chain for reasoning-tier agents (bug-fixing, iteration loops).
        execution: Model chain for execution-tier agents (most specialists).
        validation: Model chain for validation-tier agents (scanners, validators).
    """

    planning: ModelChain = field(
        default_factory=lambda: ModelChain("anthropic/claude-opus-4-6"),
    )
    reasoning: ModelChain = field(
        default_factory=lambda: ModelChain("anthropic/claude-opus-4-6"),
    )
    execution: ModelChain = field(
        default_factory=lambda: ModelChain("anthropic/claude-sonnet-4-6"),
    )
    validation: ModelChain = field(
        default_factory=lambda: ModelChain("anthropic/claude-haiku-4-5"),
    )

    @classmethod
    def from_settings(cls, settings: Settings) -> ModelRegistry:
        """Build a registry from the application Settings.

        Args:
            settings: Application settings containing model names and fallback chains.

        Returns:
            A new :class:`ModelRegistry` with chains populated from *settings*.
        """
        registry = cls(
            planning=ModelChain(
                primary=settings.default_planning_model,
                fallbacks=tuple(settings.planning_fallback_models),
            ),
            reasoning=ModelChain(
                primary=settings.default_reasoning_model,
                fallbacks=tuple(settings.reasoning_fallback_models),
            ),
            execution=ModelChain(
                primary=settings.default_execution_model,
                fallbacks=tuple(settings.execution_fallback_models),
            ),
            validation=ModelChain(
                primary=settings.default_validation_model,
                fallbacks=tuple(settings.validation_fallback_models),
            ),
        )
        logger.info(
            "model_registry_created",
            planning=registry.planning.primary,
            reasoning=registry.reasoning.primary,
            execution=registry.execution.primary,
            validation=registry.validation.primary,
        )
        return registry

    def get_chain(self, tier: ModelTier) -> ModelChain:
        """Return the model chain for a given tier.

        Args:
            tier: One of ``PLANNING``, ``REASONING``, ``EXECUTION``, or ``VALIDATION``.

        Returns:
            The :class:`ModelChain` assigned to *tier*.
        """
        mapping = {
            ModelTier.PLANNING: self.planning,
            ModelTier.REASONING: self.reasoning,
            ModelTier.EXECUTION: self.execution,
            ModelTier.VALIDATION: self.validation,
        }
        return mapping[tier]

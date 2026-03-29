"""Model registry mapping agent tiers to LLM model names (FR-TL-006)."""

from __future__ import annotations

from dataclasses import dataclass, field

from colette.config import Settings
from colette.schemas.agent_config import ModelTier


@dataclass(frozen=True)
class ModelChain:
    """A primary model plus ordered fallback alternatives."""

    primary: str
    fallbacks: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelRegistry:
    """Resolves agent model tiers to concrete model names from settings.

    Immutable after construction — create a new instance if settings change.
    """

    planning: ModelChain = field(default_factory=lambda: ModelChain("claude-opus-4-6-20250610"))
    execution: ModelChain = field(default_factory=lambda: ModelChain("claude-sonnet-4-6-20250514"))
    validation: ModelChain = field(
        default_factory=lambda: ModelChain("claude-haiku-4-5-20251001")
    )

    @classmethod
    def from_settings(cls, settings: Settings) -> ModelRegistry:
        """Build a registry from the application Settings."""
        return cls(
            planning=ModelChain(
                primary=settings.default_planning_model,
                fallbacks=tuple(settings.planning_fallback_models),
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

    def get_chain(self, tier: ModelTier) -> ModelChain:
        """Return the model chain for a given tier."""
        mapping = {
            ModelTier.PLANNING: self.planning,
            ModelTier.EXECUTION: self.execution,
            ModelTier.VALIDATION: self.validation,
        }
        return mapping[tier]

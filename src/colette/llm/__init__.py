"""LLM gateway: ChatModel factory with fallback chains (FR-TL-006, FR-ORC-014)."""

from colette.llm.gateway import create_chat_model
from colette.llm.models import ModelRegistry
from colette.llm.token_counter import estimate_tokens

__all__ = [
    "ModelRegistry",
    "create_chat_model",
    "estimate_tokens",
]

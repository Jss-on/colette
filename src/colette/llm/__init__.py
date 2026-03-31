"""LLM gateway: ChatModel factory with fallback chains (FR-TL-006, FR-ORC-014)."""

from colette.llm.gateway import GuardedChatModel, create_chat_model
from colette.llm.models import ModelRegistry
from colette.llm.registry import ProjectNotActiveError, project_status_registry
from colette.llm.token_counter import estimate_tokens

__all__ = [
    "GuardedChatModel",
    "ModelRegistry",
    "ProjectNotActiveError",
    "create_chat_model",
    "estimate_tokens",
    "project_status_registry",
]

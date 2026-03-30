"""Memory layer exceptions (FR-MEM-003/009/004)."""

from __future__ import annotations


class ColetteMemoryError(Exception):
    """Base exception for all memory layer errors."""


class ScopeViolationError(ColetteMemoryError):
    """Raised when an agent attempts cross-scope memory access (FR-MEM-003)."""

    def __init__(self, agent_scope: str, target_scope: str) -> None:
        self.agent_scope = agent_scope
        self.target_scope = target_scope
        super().__init__(
            f"Scope violation: agent in scope '{agent_scope}' cannot access scope '{target_scope}'"
        )


class ConflictDetectedError(ColetteMemoryError):
    """Raised when contradictory memory writes are detected (FR-MEM-009)."""

    def __init__(self, existing_id: str, incoming_content: str) -> None:
        self.existing_id = existing_id
        self.incoming_content = incoming_content
        super().__init__(
            f"Contradiction detected with existing memory '{existing_id}'. "
            "Flagged for human resolution."
        )


class BudgetExceededError(ColetteMemoryError):
    """Raised when an agent's context budget is exceeded (FR-MEM-004)."""

    def __init__(self, slot: str, used: int, limit: int) -> None:
        self.slot = slot
        self.used = used
        self.limit = limit
        super().__init__(
            f"Budget exceeded for slot '{slot}': {used} tokens used, limit is {limit}"
        )


class MemoryBackendError(ColetteMemoryError):
    """Raised when a memory backend (Mem0, pgvector, etc.) fails."""

    def __init__(self, backend: str, detail: str) -> None:
        self.backend = backend
        self.detail = detail
        super().__init__(f"Memory backend '{backend}' error: {detail}")


class KnowledgeGraphUnavailableError(ColetteMemoryError):
    """Raised when the knowledge graph is disabled or unreachable."""

    def __init__(self, reason: str = "Knowledge graph is disabled") -> None:
        self.reason = reason
        super().__init__(reason)

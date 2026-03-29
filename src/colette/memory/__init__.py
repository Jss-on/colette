"""Memory layer -- hot/warm/cold tiers, RAG pipeline, knowledge graph (FR-MEM-*).

Public API re-exports for convenient access:

    from colette.memory import MemorySettings, MemoryEntry, MemoryScope
"""

from colette.memory.config import MemorySettings
from colette.memory.context import ContextBudgetTracker, HistoryManager, VerbatimCompactor
from colette.memory.exceptions import (
    BudgetExceededError,
    ColetteMemoryError,
    ConflictDetectedError,
    KnowledgeGraphUnavailableError,
    MemoryBackendError,
    ScopeViolationError,
)
from colette.memory.manager import MemoryManager
from colette.memory.models import (
    ChunkRecord,
    CompactionResult,
    ConflictReport,
    ConflictType,
    KGEntity,
    KGRelationship,
    MemoryEntry,
    MemoryScope,
    MemoryWriteResult,
    RAGTriadResult,
    RetrievalResult,
)

__all__ = [
    "BudgetExceededError",
    "ChunkRecord",
    "ColetteMemoryError",
    "CompactionResult",
    "ConflictDetectedError",
    "ConflictReport",
    "ConflictType",
    "ContextBudgetTracker",
    "HistoryManager",
    "KGEntity",
    "KGRelationship",
    "KnowledgeGraphUnavailableError",
    "MemoryBackendError",
    "MemoryEntry",
    "MemoryManager",
    "MemoryScope",
    "MemorySettings",
    "MemoryWriteResult",
    "RAGTriadResult",
    "RetrievalResult",
    "ScopeViolationError",
    "VerbatimCompactor",
]

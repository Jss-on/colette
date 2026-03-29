"""Memory layer domain models (FR-MEM-001/002/007/009).

All models are frozen dataclasses for safe sharing across async boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

# ── Enums ────────────────────────────────────────────────────────────────


class MemoryScope(StrEnum):
    """Scoping levels for project memory (FR-MEM-003)."""

    PRIVATE = "private"  # visible only to the owning agent
    SHARED = "shared"  # visible to all agents within a stage
    GLOBAL = "global"  # visible to all agents across stages


class MemoryWriteResult(StrEnum):
    """Outcome of a memory write operation (FR-MEM-011)."""

    ADDED = "added"
    UPDATED = "updated"
    DELETED = "deleted"
    SKIPPED = "skipped"
    CONFLICT_FLAGGED = "conflict_flagged"


class ConflictType(StrEnum):
    """Classification of memory conflicts (FR-MEM-009)."""

    SAME = "same"  # duplicate — skip
    UPDATE = "update"  # supersedes — update
    CONTRADICTION = "contradiction"  # conflicting — flag


# ── Memory entry ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MemoryEntry:
    """A single memory record stored via Mem0 (FR-MEM-001)."""

    id: str
    project_id: str
    content: str
    scope: MemoryScope = MemoryScope.SHARED

    user_id: str = ""
    agent_id: str = ""
    metadata: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    confidence: float = 1.0
    is_permanent: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None

    @property
    def metadata_dict(self) -> dict[str, str]:
        return dict(self.metadata)


# ── Knowledge graph types ────────────────────────────────────────────────


@dataclass(frozen=True)
class KGEntity:
    """A knowledge graph node with bi-temporal tracking (FR-MEM-002/008)."""

    id: str
    project_id: str
    entity_type: str
    name: str
    properties: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    # Transaction time (when we learned about it)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expired_at: datetime | None = None

    # Valid time (when the fact is/was true in the real world)
    valid_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    invalid_at: datetime | None = None

    @property
    def properties_dict(self) -> dict[str, str]:
        return dict(self.properties)


@dataclass(frozen=True)
class KGRelationship:
    """A knowledge graph edge with bi-temporal tracking (FR-MEM-002/008)."""

    id: str
    project_id: str
    source_id: str
    target_id: str
    relationship_type: str
    properties: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expired_at: datetime | None = None
    valid_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    invalid_at: datetime | None = None

    @property
    def properties_dict(self) -> dict[str, str]:
        return dict(self.properties)


# ── RAG types ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ChunkRecord:
    """A text chunk in the RAG index (FR-MEM-007)."""

    id: str
    project_id: str
    source_path: str
    content: str
    token_count: int
    chunk_index: int
    total_chunks: int
    embedding: tuple[float, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RetrievalResult:
    """A single retrieval hit from the RAG pipeline (FR-MEM-007)."""

    chunk: ChunkRecord
    score: float
    source: str  # e.g. "bm25", "dense", "rrf", "reranked"
    retrieval_method: str = ""


# ── Conflict / compaction types ──────────────────────────────────────────


@dataclass(frozen=True)
class ConflictReport:
    """Report of a detected memory conflict (FR-MEM-009)."""

    existing_entry: MemoryEntry
    incoming_content: str
    similarity_score: float
    conflict_type: ConflictType
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class CompactionResult:
    """Result of context compaction (FR-MEM-005)."""

    original_tokens: int
    compacted_tokens: int
    reduction_ratio: float
    compacted_content: str


@dataclass(frozen=True)
class RAGTriadResult:
    """RAG Triad evaluation scores (FR-MEM-013)."""

    faithfulness: float
    context_relevance: float
    answer_relevance: float
    alert_triggered: bool = False

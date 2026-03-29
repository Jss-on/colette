"""Protocol interfaces for memory layer backends (FR-MEM-001/002/007).

All external dependencies are accessed through these protocols, enabling
dependency injection and testability.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from colette.memory.models import (
    ChunkRecord,
    CompactionResult,
    ConflictReport,
    KGEntity,
    KGRelationship,
    MemoryEntry,
    MemoryScope,
    RetrievalResult,
)


@runtime_checkable
class ProjectMemoryStore(Protocol):
    """Interface for project/user memory storage (FR-MEM-001)."""

    async def store(self, entry: MemoryEntry) -> str:
        """Store a memory entry. Returns the entry ID."""
        ...

    async def retrieve(
        self,
        project_id: str,
        query: str,
        *,
        scope: MemoryScope = MemoryScope.SHARED,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """Retrieve memories matching a query within scope."""
        ...

    async def update(
        self,
        entry_id: str,
        content: str,
        metadata: dict[str, str] | None = None,
    ) -> MemoryEntry:
        """Update an existing memory entry."""
        ...

    async def delete(self, entry_id: str) -> None:
        """Delete a memory entry by ID."""
        ...

    async def search(
        self,
        project_id: str,
        query: str,
        *,
        scope: MemoryScope = MemoryScope.SHARED,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """Semantic search for memories within scope."""
        ...


@runtime_checkable
class KnowledgeGraphStore(Protocol):
    """Interface for the knowledge graph backend (FR-MEM-002)."""

    async def add_entity(self, entity: KGEntity) -> str:
        """Add a node. Returns the entity ID."""
        ...

    async def add_relationship(self, rel: KGRelationship) -> str:
        """Add an edge. Returns the relationship ID."""
        ...

    async def get_entity(self, entity_id: str) -> KGEntity | None:
        """Retrieve a single entity by ID."""
        ...

    async def get_neighbors(
        self,
        entity_id: str,
        *,
        hops: int = 1,
    ) -> list[KGEntity]:
        """Return entities within *hops* of the given entity."""
        ...

    async def query_temporal(
        self,
        project_id: str,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[KGEntity]:
        """Query entities modified between *since* and *until* (FR-MEM-008)."""
        ...

    async def delete_entity(self, entity_id: str) -> None:
        """Soft-delete an entity by setting expired_at."""
        ...


@runtime_checkable
class ChunkIndexer(Protocol):
    """Interface for the RAG chunk index (FR-MEM-007)."""

    async def index_chunks(self, chunks: list[ChunkRecord]) -> int:
        """Index a batch of chunks. Returns count inserted."""
        ...

    async def delete_by_source(self, source_path: str) -> int:
        """Delete all chunks for a source path. Returns count deleted."""
        ...


@runtime_checkable
class ContextRetriever(Protocol):
    """Interface for RAG context retrieval (FR-MEM-007)."""

    async def retrieve(
        self,
        project_id: str,
        query: str,
        *,
        top_k: int = 60,
    ) -> list[RetrievalResult]:
        """Retrieve relevant context for a query."""
        ...


@runtime_checkable
class Reranker(Protocol):
    """Interface for result reranking (FR-MEM-007)."""

    async def rerank(
        self,
        query: str,
        results: list[RetrievalResult],
        *,
        top_n: int = 5,
    ) -> list[RetrievalResult]:
        """Rerank results and return top_n."""
        ...


class ContextCompactor(Protocol):
    """Interface for context compaction (FR-MEM-005)."""

    def compact(self, content: str, target_tokens: int) -> CompactionResult:
        """Compact content to fit within target_tokens."""
        ...


@runtime_checkable
class ConflictDetector(Protocol):
    """Interface for memory conflict detection (FR-MEM-009)."""

    async def detect(
        self,
        existing: MemoryEntry,
        incoming_content: str,
    ) -> ConflictReport | None:
        """Check if incoming content contradicts an existing entry.

        Returns a ConflictReport if conflict detected, None otherwise.
        """
        ...

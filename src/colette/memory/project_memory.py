"""Mem0 project memory integration (FR-MEM-001/003/012).

Wraps the ``mem0ai`` library behind the :class:`ProjectMemoryStore`
protocol so the implementation can be swapped if the 0.1.x API is
unstable.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog

from colette.memory.config import MemorySettings
from colette.memory.exceptions import (
    MemoryBackendError,
    ScopeViolationError,
)
from colette.memory.models import MemoryEntry, MemoryScope

logger = structlog.get_logger(__name__)


def _dict_to_tuples(d: dict[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted(d.items()))


class Mem0ProjectMemoryStore:
    """Mem0-backed implementation of :class:`ProjectMemoryStore`.

    All operations are scoped by ``project_id``.  Cross-scope access
    raises :class:`ScopeViolationError` per FR-MEM-003.
    """

    def __init__(self, settings: MemorySettings) -> None:
        self._settings = settings
        self._client: Any = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                from mem0 import Memory  # type: ignore[import-untyped]

                self._client = Memory()
            except Exception as exc:
                raise MemoryBackendError("mem0", str(exc)) from exc
        return self._client

    # ── Scope enforcement (FR-MEM-003) ──────────────────────────────

    @staticmethod
    def _check_scope(
        agent_scope: MemoryScope,
        target_scope: MemoryScope,
    ) -> None:
        if agent_scope == MemoryScope.PRIVATE and target_scope != MemoryScope.PRIVATE:
            raise ScopeViolationError(agent_scope.value, target_scope.value)
        if agent_scope == MemoryScope.SHARED and target_scope == MemoryScope.PRIVATE:
            raise ScopeViolationError(agent_scope.value, target_scope.value)

    # ── CRUD operations ─────────────────────────────────────────────

    async def store(self, entry: MemoryEntry) -> str:
        """Store a memory entry. Returns the assigned ID."""
        client = self._ensure_client()
        meta = {
            "project_id": entry.project_id,
            "scope": entry.scope.value,
            "agent_id": entry.agent_id,
            "user_id": entry.user_id,
            "is_permanent": str(entry.is_permanent),
            "confidence": str(entry.confidence),
            **entry.metadata_dict,
        }
        try:
            result = client.add(
                entry.content,
                user_id=entry.project_id,
                metadata=meta,
            )
            entry_id = result.get("id", entry.id or str(uuid.uuid4()))
        except Exception as exc:
            raise MemoryBackendError("mem0", str(exc)) from exc

        logger.info(
            "memory_stored",
            entry_id=entry_id,
            project_id=entry.project_id,
            scope=entry.scope.value,
        )
        return str(entry_id)

    async def retrieve(
        self,
        project_id: str,
        query: str,
        *,
        scope: MemoryScope = MemoryScope.SHARED,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """Retrieve memories matching *query* within *scope*."""
        return await self.search(project_id, query, scope=scope, limit=limit)

    async def update(
        self,
        entry_id: str,
        content: str,
        metadata: dict[str, str] | None = None,
    ) -> MemoryEntry:
        """Update an existing memory entry."""
        client = self._ensure_client()
        try:
            client.update(entry_id, data=content, metadata=metadata)
        except Exception as exc:
            raise MemoryBackendError("mem0", str(exc)) from exc

        logger.info("memory_updated", entry_id=entry_id)
        return MemoryEntry(
            id=entry_id,
            project_id="",
            content=content,
            metadata=_dict_to_tuples(metadata) if metadata else (),
            updated_at=datetime.now(UTC),
        )

    async def delete(self, entry_id: str) -> None:
        """Delete a memory entry by ID."""
        client = self._ensure_client()
        try:
            client.delete(entry_id)
        except Exception as exc:
            raise MemoryBackendError("mem0", str(exc)) from exc

        logger.info("memory_deleted", entry_id=entry_id)

    async def search(
        self,
        project_id: str,
        query: str,
        *,
        scope: MemoryScope = MemoryScope.SHARED,
        agent_scope: MemoryScope = MemoryScope.SHARED,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """Semantic search with scope enforcement (FR-MEM-003)."""
        self._check_scope(agent_scope, scope)

        client = self._ensure_client()
        try:
            results = client.search(
                query,
                user_id=project_id,
                limit=limit,
            )
        except Exception as exc:
            raise MemoryBackendError("mem0", str(exc)) from exc

        entries: list[MemoryEntry] = []
        for item in results.get("results", results) if isinstance(results, dict) else results:
            meta = item.get("metadata", {})
            item_scope = MemoryScope(meta.get("scope", "shared"))
            if item_scope != scope and scope != MemoryScope.GLOBAL:
                continue
            entries.append(
                MemoryEntry(
                    id=str(item.get("id", "")),
                    project_id=project_id,
                    content=str(item.get("memory", item.get("text", ""))),
                    scope=item_scope,
                    agent_id=meta.get("agent_id", ""),
                    user_id=meta.get("user_id", ""),
                    confidence=float(meta.get("confidence", 1.0)),
                    is_permanent=meta.get("is_permanent", "False").lower() == "true",
                    metadata=_dict_to_tuples(
                        {k: str(v) for k, v in meta.items() if k not in {
                            "project_id", "scope", "agent_id", "user_id",
                            "is_permanent", "confidence",
                        }}
                    ),
                )
            )
        return entries[:limit]

    # ── Decay (FR-MEM-012) ──────────────────────────────────────────

    async def apply_decay(
        self,
        project_id: str,
        current_time: datetime,
    ) -> int:
        """Soft-delete memories past their decay threshold.

        Permanent memories are exempt.  Only runs when decay is enabled.
        Returns count of decayed memories.
        """
        if not self._settings.decay_enabled:
            return 0

        half_life_hours = self._settings.decay_default_half_life_hours
        all_memories = await self.search(
            project_id, "", scope=MemoryScope.GLOBAL, limit=1000
        )
        decayed = 0
        for mem in all_memories:
            if mem.is_permanent:
                continue
            age_hours = (current_time - mem.updated_at).total_seconds() / 3600
            decay_score = math.pow(0.5, age_hours / half_life_hours)
            if decay_score < 0.1:
                await self.delete(mem.id)
                decayed += 1
                logger.info(
                    "memory_decayed",
                    entry_id=mem.id,
                    age_hours=round(age_hours, 1),
                    decay_score=round(decay_score, 4),
                )
        return decayed

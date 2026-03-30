"""Memory write pipeline with quality gates (FR-MEM-011).

Implements: extract facts -> search existing -> compare -> CRUD decision.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import structlog

from colette.memory.conflict_detector import HybridConflictDetector
from colette.memory.models import (
    ConflictType,
    MemoryEntry,
    MemoryScope,
    MemoryWriteResult,
)
from colette.memory.protocols import ProjectMemoryStore

logger = structlog.get_logger(__name__)


def _extract_facts(content: str) -> list[str]:
    """Extract discrete factual claims from content.

    Simple heuristic: split by sentences, filter for declarative
    statements (not questions or very short fragments).
    """
    sentences = re.split(r"[.!?\n]+", content)
    facts: list[str] = []
    for s in sentences:
        s = s.strip()
        if len(s) < 10:
            continue
        if s.endswith("?"):
            continue
        facts.append(s)
    return facts if facts else [content.strip()] if content.strip() else []


@dataclass(frozen=True)
class WriteDecision:
    """Result of processing a single fact through the write pipeline."""

    fact: str
    result: MemoryWriteResult
    existing_id: str | None = None
    new_id: str | None = None


class MemoryWritePipeline:
    """Processes memory writes through quality gates.

    Pipeline:
    1. Extract key facts from content
    2. Search existing memories for matches
    3. Compare via conflict detector
    4. CRUD decision: ADDED, UPDATED, SKIPPED, CONFLICT_FLAGGED
    """

    def __init__(
        self,
        memory_store: ProjectMemoryStore,
        conflict_detector: HybridConflictDetector | None = None,
    ) -> None:
        self._store = memory_store
        self._detector = conflict_detector or HybridConflictDetector()

    async def process_write(
        self,
        project_id: str,
        content: str,
        *,
        scope: MemoryScope = MemoryScope.SHARED,
        agent_id: str = "",
        metadata: dict[str, str] | None = None,
    ) -> list[WriteDecision]:
        """Process a memory write through the quality gate pipeline.

        Returns a list of WriteDecision for each extracted fact.
        """
        facts = _extract_facts(content)
        if not facts:
            return []

        decisions: list[WriteDecision] = []
        for fact in facts:
            decision = await self._process_fact(
                project_id=project_id,
                fact=fact,
                scope=scope,
                agent_id=agent_id,
                metadata=metadata,
            )
            decisions.append(decision)

        logger.info(
            "write_pipeline_complete",
            project_id=project_id,
            facts=len(facts),
            results={
                d.result.value: sum(1 for x in decisions if x.result == d.result)
                for d in decisions
            },
        )
        return decisions

    async def _process_fact(
        self,
        project_id: str,
        fact: str,
        scope: MemoryScope,
        agent_id: str,
        metadata: dict[str, str] | None,
    ) -> WriteDecision:
        """Process a single fact through search -> compare -> CRUD."""
        # Search for existing memories
        existing = await self._store.search(project_id, fact, scope=scope, limit=5)

        if not existing:
            # No match — add new
            entry = MemoryEntry(
                id="",
                project_id=project_id,
                content=fact,
                scope=scope,
                agent_id=agent_id,
                metadata=tuple(sorted((metadata or {}).items())),
            )
            new_id = await self._store.store(entry)
            return WriteDecision(fact=fact, result=MemoryWriteResult.ADDED, new_id=new_id)

        # Check each match for conflicts
        for mem in existing:
            report = await self._detector.detect(mem, fact)
            if report is None:
                continue

            if report.conflict_type == ConflictType.SAME:
                logger.debug("write_skipped_duplicate", existing_id=mem.id)
                return WriteDecision(
                    fact=fact,
                    result=MemoryWriteResult.SKIPPED,
                    existing_id=mem.id,
                )

            if report.conflict_type == ConflictType.UPDATE:
                await self._store.update(mem.id, fact, metadata)
                return WriteDecision(
                    fact=fact,
                    result=MemoryWriteResult.UPDATED,
                    existing_id=mem.id,
                )

            if report.conflict_type == ConflictType.CONTRADICTION:
                logger.warning(
                    "write_conflict_flagged",
                    existing_id=mem.id,
                    incoming=fact[:100],
                )
                return WriteDecision(
                    fact=fact,
                    result=MemoryWriteResult.CONFLICT_FLAGGED,
                    existing_id=mem.id,
                )

        # No conflict with any match — add new
        entry = MemoryEntry(
            id="",
            project_id=project_id,
            content=fact,
            scope=scope,
            agent_id=agent_id,
            metadata=tuple(sorted((metadata or {}).items())),
        )
        new_id = await self._store.store(entry)
        return WriteDecision(fact=fact, result=MemoryWriteResult.ADDED, new_id=new_id)

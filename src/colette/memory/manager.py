"""MemoryManager facade — single entry point for the memory layer.

Composes all memory subsystems: project memory, knowledge graph,
RAG pipeline, context management, write pipeline.
"""

from __future__ import annotations

from typing import Any

import structlog

from colette.memory.config import MemorySettings
from colette.memory.conflict_detector import HybridConflictDetector
from colette.memory.context.budget_tracker import ContextBudgetTracker
from colette.memory.context.compactor import VerbatimCompactor
from colette.memory.context.history_manager import HistoryManager
from colette.memory.knowledge_graph import (
    GraphitiKnowledgeGraphStore,
    NullKnowledgeGraphStore,
)
from colette.memory.models import (
    CompactionResult,
    KGEntity,
    KGRelationship,
    MemoryScope,
    RetrievalResult,
)
from colette.memory.project_memory import Mem0ProjectMemoryStore
from colette.memory.rag.evaluator import RAGTriadEvaluator
from colette.memory.rag.indexer import PgVectorIndexer
from colette.memory.rag.reranker import create_reranker
from colette.memory.rag.retriever import HybridRetriever
from colette.memory.write_pipeline import MemoryWritePipeline, WriteDecision

logger = structlog.get_logger(__name__)


class MemoryManager:
    """Unified facade for all memory layer operations.

    Usage::

        manager = MemoryManager.create(settings)
        await manager.store_memory("proj-1", "The API uses REST", scope=MemoryScope.SHARED)
        results = await manager.retrieve_context("proj-1", "API design")
    """

    def __init__(
        self,
        settings: MemorySettings,
        project_memory: Mem0ProjectMemoryStore,
        knowledge_graph: NullKnowledgeGraphStore | GraphitiKnowledgeGraphStore,
        write_pipeline: MemoryWritePipeline,
        retriever: HybridRetriever,
        reranker: Any,
        evaluator: RAGTriadEvaluator,
        compactor: VerbatimCompactor,
    ) -> None:
        self._settings = settings
        self.project_memory = project_memory
        self.knowledge_graph = knowledge_graph
        self._write_pipeline = write_pipeline
        self._retriever = retriever
        self._reranker = reranker
        self._evaluator = evaluator
        self._compactor = compactor

    @classmethod
    def create(cls, settings: MemorySettings) -> MemoryManager:
        """Factory that wires all memory subsystems together."""
        project_memory = Mem0ProjectMemoryStore(settings)

        if settings.knowledge_graph_enabled:
            try:
                kg: NullKnowledgeGraphStore | GraphitiKnowledgeGraphStore = (
                    GraphitiKnowledgeGraphStore(settings)
                )
            except Exception:
                logger.warning("kg_fallback_to_null")
                kg = NullKnowledgeGraphStore()
        else:
            kg = NullKnowledgeGraphStore()

        indexer = PgVectorIndexer(settings)
        retriever = HybridRetriever(indexer, settings)
        reranker = create_reranker(settings)
        evaluator = RAGTriadEvaluator(settings)
        compactor = VerbatimCompactor()
        conflict_detector = HybridConflictDetector()
        write_pipeline = MemoryWritePipeline(project_memory, conflict_detector)

        return cls(
            settings=settings,
            project_memory=project_memory,
            knowledge_graph=kg,
            write_pipeline=write_pipeline,
            retriever=retriever,
            reranker=reranker,
            evaluator=evaluator,
            compactor=compactor,
        )

    # ── Memory writes ───────────────────────────────────────────────

    async def store_memory(
        self,
        project_id: str,
        content: str,
        *,
        scope: MemoryScope = MemoryScope.SHARED,
        agent_id: str = "",
        metadata: dict[str, str] | None = None,
    ) -> list[WriteDecision]:
        """Store memory through the write quality gate pipeline."""
        return await self._write_pipeline.process_write(
            project_id=project_id,
            content=content,
            scope=scope,
            agent_id=agent_id,
            metadata=metadata,
        )

    # ── Context retrieval ───────────────────────────────────────────

    async def retrieve_context(
        self,
        project_id: str,
        query: str,
        *,
        top_k: int = 5,
    ) -> list[RetrievalResult]:
        """Full RAG pipeline: retrieve -> rerank -> return top results."""
        raw_results = await self._retriever.retrieve(
            project_id, query, top_k=self._settings.rag_retrieval_k
        )
        reranked = list(await self._reranker.rerank(query, raw_results, top_n=top_k))

        logger.info(
            "context_retrieved",
            project_id=project_id,
            raw_count=len(raw_results),
            reranked_count=len(reranked),
        )
        return reranked

    # ── Context management ──────────────────────────────────────────

    def create_budget_tracker(
        self,
        agent_role: str,
        total_budget: int,
        allocations: tuple[tuple[str, float], ...] | None = None,
    ) -> ContextBudgetTracker:
        """Create a new budget tracker for an agent."""
        kwargs: dict[str, Any] = {
            "agent_role": agent_role,
            "total_budget": total_budget,
        }
        if allocations is not None:
            kwargs["slot_allocations"] = allocations
        return ContextBudgetTracker(**kwargs)

    def compact_if_needed(
        self,
        content: str,
        budget_tracker: ContextBudgetTracker,
    ) -> tuple[str, CompactionResult | None]:
        """Compact content if the budget tracker indicates compaction is needed."""
        if not budget_tracker.needs_compaction(self._settings.compaction_threshold):
            return content, None

        target_tokens = int(budget_tracker.total_budget * 0.5)
        result = self._compactor.compact(content, target_tokens)
        return result.compacted_content, result

    def create_history_manager(
        self,
        recent_count: int | None = None,
    ) -> HistoryManager:
        """Create a new conversation history manager."""
        return HistoryManager(recent_count=recent_count or self._settings.history_recent_count)

    # ── Knowledge graph ─────────────────────────────────────────────

    async def add_to_knowledge_graph(
        self,
        entity: KGEntity | KGRelationship,
    ) -> str:
        """Add an entity or relationship to the knowledge graph."""
        if isinstance(entity, KGEntity):
            return await self.knowledge_graph.add_entity(entity)
        return await self.knowledge_graph.add_relationship(entity)

    async def query_knowledge_graph(
        self,
        entity_id: str,
        *,
        hops: int = 1,
    ) -> list[KGEntity]:
        """Query the knowledge graph for neighbors."""
        return await self.knowledge_graph.get_neighbors(entity_id, hops=hops)

    # ── RAG evaluation ──────────────────────────────────────────────

    async def evaluate_retrieval(
        self,
        query: str,
        context: list[str],
        response: str,
    ) -> Any:
        """Evaluate a RAG retrieval using the RAG Triad."""
        return await self._evaluator.evaluate(query, context, response)

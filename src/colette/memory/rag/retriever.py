"""Hybrid BM25 + dense retriever with RRF fusion (FR-MEM-007).

Combines lexical (BM25) and semantic (pgvector) search results
using Reciprocal Rank Fusion.
"""

from __future__ import annotations

from typing import Any

import structlog

from colette.memory.config import MemorySettings
from colette.memory.models import RetrievalResult
from colette.memory.rag.indexer import PgVectorIndexer

logger = structlog.get_logger(__name__)

# RRF constant (standard value from the literature)
_RRF_K = 60


def _reciprocal_rank_fusion(
    result_lists: list[list[RetrievalResult]],
    k: int = _RRF_K,
) -> list[RetrievalResult]:
    """Merge multiple ranked lists using Reciprocal Rank Fusion.

    RRF(d) = sum(1 / (k + rank_i(d))) for each list i.
    """
    scores: dict[str, float] = {}
    best_result: dict[str, RetrievalResult] = {}

    for results in result_lists:
        for rank, result in enumerate(results):
            chunk_id = result.chunk.id
            rrf_score = 1.0 / (k + rank + 1)
            scores[chunk_id] = scores.get(chunk_id, 0.0) + rrf_score
            if chunk_id not in best_result or result.score > best_result[chunk_id].score:
                best_result[chunk_id] = result

    # Sort by RRF score descending
    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [
        RetrievalResult(
            chunk=best_result[cid].chunk,
            score=scores[cid],
            source="rrf",
            retrieval_method="rrf(bm25+dense)",
        )
        for cid in sorted_ids
    ]


def _position_aware_reorder(results: list[RetrievalResult]) -> list[RetrievalResult]:
    """Reorder results for primacy/recency bias optimization.

    Highest-relevance at the beginning and end of the list.
    """
    if len(results) <= 2:
        return results

    sorted_by_score = sorted(results, key=lambda r: r.score, reverse=True)
    left = True
    front: list[RetrievalResult] = []
    back: list[RetrievalResult] = []

    for item in sorted_by_score:
        if left:
            front.append(item)
        else:
            back.append(item)
        left = not left

    return front + list(reversed(back))


class HybridRetriever:
    """Hybrid BM25 + dense retriever with RRF fusion.

    Implements the ContextRetriever protocol.
    """

    def __init__(
        self,
        indexer: PgVectorIndexer,
        settings: MemorySettings | None = None,
    ) -> None:
        self._indexer = indexer
        self._settings = settings or MemorySettings()
        self._bm25_indexes: dict[str, Any] = {}

    async def retrieve(
        self,
        project_id: str,
        query: str,
        *,
        top_k: int = 60,
    ) -> list[RetrievalResult]:
        """Hybrid retrieval: BM25 + dense + RRF fusion."""
        # Dense retrieval
        query_embedding = await self._get_query_embedding(query)
        dense_results = await self._indexer.search_dense(project_id, query_embedding, top_k=top_k)

        # BM25 retrieval
        bm25_results = self._bm25_search(project_id, query, dense_results, top_k)

        # RRF fusion
        fused = _reciprocal_rank_fusion([bm25_results, dense_results])

        # Position-aware reordering
        final = _position_aware_reorder(fused[:top_k])

        logger.info(
            "hybrid_retrieval",
            project_id=project_id,
            dense_count=len(dense_results),
            bm25_count=len(bm25_results),
            fused_count=len(final),
        )
        return final

    def _bm25_search(
        self,
        project_id: str,
        query: str,
        corpus_results: list[RetrievalResult],
        top_k: int,
    ) -> list[RetrievalResult]:
        """BM25 search using the dense results as corpus."""
        if not corpus_results:
            return []

        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            logger.warning("rank_bm25_not_installed")
            return []

        corpus = [r.chunk.content.lower().split() for r in corpus_results]
        bm25 = BM25Okapi(corpus)
        query_tokens = query.lower().split()
        scores = bm25.get_scores(query_tokens)

        scored_results = [
            RetrievalResult(
                chunk=corpus_results[i].chunk,
                score=float(scores[i]),
                source="bm25",
            )
            for i in range(len(corpus_results))
        ]
        scored_results.sort(key=lambda r: r.score, reverse=True)
        return scored_results[:top_k]

    async def _get_query_embedding(self, query: str) -> list[float]:
        """Generate embedding for the query text."""
        from colette.llm.embeddings import generate_embeddings

        vectors = await generate_embeddings(
            [query],
            model=self._settings.embedding_model,
            api_key=self._settings.embeddings_api_key,
            base_url=self._settings.embeddings_base_url,
        )
        return vectors[0]

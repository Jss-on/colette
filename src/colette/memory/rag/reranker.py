"""Result reranking (FR-MEM-007).

Cohere reranker with NoOp fallback when the API key is unavailable.
"""

from __future__ import annotations

import structlog

from colette.memory.config import MemorySettings
from colette.memory.models import RetrievalResult

logger = structlog.get_logger(__name__)


class NoOpReranker:
    """Fallback reranker that simply truncates to top_n.

    Used when Cohere API key is unavailable.
    """

    async def rerank(
        self,
        query: str,
        results: list[RetrievalResult],
        *,
        top_n: int = 5,
    ) -> list[RetrievalResult]:
        return results[:top_n]


class CohereReranker:
    """Cohere-backed reranker implementing the Reranker protocol.

    Takes top ``rag_rerank_candidates`` and returns top ``top_n``.
    Falls back to NoOpReranker if the API key is empty.
    """

    def __init__(self, settings: MemorySettings | None = None) -> None:
        self._settings = settings or MemorySettings()
        self._client = None

    def _ensure_client(self) -> object:
        if self._client is None:
            if not self._settings.cohere_api_key:
                raise _NoApiKeyError
            try:
                import cohere  # type: ignore[import-untyped]

                self._client = cohere.ClientV2(self._settings.cohere_api_key)
            except Exception as exc:
                logger.warning("cohere_init_failed", error=str(exc))
                raise _NoApiKeyError from exc
        return self._client

    async def rerank(
        self,
        query: str,
        results: list[RetrievalResult],
        *,
        top_n: int = 5,
    ) -> list[RetrievalResult]:
        candidates = results[: self._settings.rag_rerank_candidates]
        if not candidates:
            return []

        try:
            client = self._ensure_client()
        except _NoApiKeyError:
            logger.warning("cohere_fallback_to_noop")
            return await NoOpReranker().rerank(query, results, top_n=top_n)

        documents = [r.chunk.content for r in candidates]
        try:
            response = client.rerank(  # type: ignore[union-attr]
                model=self._settings.cohere_api_key and "rerank-v3.5",
                query=query,
                documents=documents,
                top_n=top_n,
            )
        except Exception as exc:
            logger.warning("cohere_rerank_failed", error=str(exc))
            return await NoOpReranker().rerank(query, results, top_n=top_n)

        reranked: list[RetrievalResult] = []
        for item in response.results:  # type: ignore[union-attr]
            idx = item.index
            reranked.append(
                RetrievalResult(
                    chunk=candidates[idx].chunk,
                    score=float(item.relevance_score),
                    source="reranked",
                    retrieval_method="cohere_rerank_v3.5",
                )
            )

        logger.info(
            "reranking_complete",
            candidates=len(candidates),
            returned=len(reranked),
        )
        return reranked


class _NoApiKeyError(Exception):
    """Internal signal that Cohere API key is missing."""


def create_reranker(settings: MemorySettings | None = None) -> CohereReranker | NoOpReranker:
    """Factory that returns the appropriate reranker based on config."""
    s = settings or MemorySettings()
    if not s.cohere_api_key:
        logger.info("reranker_using_noop", reason="no cohere api key")
        return NoOpReranker()
    return CohereReranker(s)

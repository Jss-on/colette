"""RAG Triad evaluation (FR-MEM-013).

Evaluates retrieval quality using three metrics:
- Context relevance (query vs. context)
- Faithfulness (context vs. response)
- Answer relevance (query vs. response)
"""

from __future__ import annotations

import structlog

from colette.memory.config import MemorySettings
from colette.memory.models import RAGTriadResult

logger = structlog.get_logger(__name__)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class RAGTriadEvaluator:
    """Evaluates RAG pipeline output using the RAG Triad.

    - Context relevance: embedding similarity between query and context
    - Faithfulness: LLM-based scoring of response grounding in context
    - Answer relevance: embedding similarity between query and response
    """

    def __init__(self, settings: MemorySettings | None = None) -> None:
        self._settings = settings or MemorySettings()

    async def evaluate(
        self,
        query: str,
        context: list[str],
        response: str,
        *,
        query_embedding: list[float] | None = None,
        context_embeddings: list[list[float]] | None = None,
        response_embedding: list[float] | None = None,
    ) -> RAGTriadResult:
        """Evaluate a RAG output against the triad metrics.

        When embeddings are not provided, uses simple heuristic scoring
        based on token overlap.
        """
        context_relevance = self._compute_context_relevance(
            query, context, query_embedding, context_embeddings
        )
        answer_relevance = self._compute_answer_relevance(
            query, response, query_embedding, response_embedding
        )
        faithfulness = self._compute_faithfulness(context, response)

        threshold = self._settings.rag_faithfulness_threshold
        alert = faithfulness < threshold

        if alert:
            logger.warning(
                "rag_faithfulness_alert",
                faithfulness=round(faithfulness, 3),
                threshold=threshold,
                query_preview=query[:100],
            )

        result = RAGTriadResult(
            faithfulness=round(faithfulness, 3),
            context_relevance=round(context_relevance, 3),
            answer_relevance=round(answer_relevance, 3),
            alert_triggered=alert,
        )

        logger.info(
            "rag_triad_evaluation",
            faithfulness=result.faithfulness,
            context_relevance=result.context_relevance,
            answer_relevance=result.answer_relevance,
            alert=result.alert_triggered,
        )
        return result

    def _compute_context_relevance(
        self,
        query: str,
        context: list[str],
        query_emb: list[float] | None,
        context_embs: list[list[float]] | None,
    ) -> float:
        """Score how relevant the retrieved context is to the query."""
        if query_emb and context_embs:
            scores = [_cosine_similarity(query_emb, ce) for ce in context_embs]
            return sum(scores) / len(scores) if scores else 0.0

        # Fallback: token overlap heuristic
        query_tokens = set(query.lower().split())
        if not query_tokens or not context:
            return 0.0

        overlaps = []
        for ctx in context:
            ctx_tokens = set(ctx.lower().split())
            if ctx_tokens:
                overlap = len(query_tokens & ctx_tokens) / len(query_tokens)
                overlaps.append(overlap)
        return sum(overlaps) / len(overlaps) if overlaps else 0.0

    def _compute_answer_relevance(
        self,
        query: str,
        response: str,
        query_emb: list[float] | None,
        response_emb: list[float] | None,
    ) -> float:
        """Score how relevant the response is to the query."""
        if query_emb and response_emb:
            return _cosine_similarity(query_emb, response_emb)

        # Fallback: token overlap
        query_tokens = set(query.lower().split())
        response_tokens = set(response.lower().split())
        if not query_tokens or not response_tokens:
            return 0.0
        return len(query_tokens & response_tokens) / len(query_tokens)

    def _compute_faithfulness(
        self,
        context: list[str],
        response: str,
    ) -> float:
        """Score how well the response is grounded in the context.

        Uses token overlap as a heuristic.  In production, this should
        be replaced with an LLM-based evaluation using the validation
        tier model.
        """
        if not context or not response:
            return 0.0

        context_text = " ".join(context).lower()
        context_tokens = set(context_text.split())
        response_tokens = set(response.lower().split())

        if not response_tokens:
            return 0.0

        grounded = len(response_tokens & context_tokens)
        return min(grounded / len(response_tokens), 1.0)

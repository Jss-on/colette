"""RAG Triad metrics tracking (NFR-OBS-006).

Evaluates context relevance, faithfulness, and answer relevance for
RAG-augmented agent queries and produces alerts when quality degrades.
"""

from __future__ import annotations

import structlog
from pydantic import BaseModel

logger = structlog.get_logger(__name__)


# ── Data models ────────────────────────────────────────────────────────


class RAGTriadScore(BaseModel, frozen=True):
    """Immutable RAG Triad evaluation for a single query.

    Attributes:
        context_relevance: Score (0.0--1.0) for how relevant retrieved context is.
        faithfulness: Score (0.0--1.0) for how grounded the answer is in context.
        answer_relevance: Score (0.0--1.0) for how relevant the answer is to the query.
        query: The original user query.
        retrieved_count: Number of chunks retrieved for this query.
        timestamp: ISO-8601 timestamp of the evaluation.
    """

    context_relevance: float
    faithfulness: float
    answer_relevance: float
    query: str
    retrieved_count: int
    timestamp: str


class RAGTriadAlert(BaseModel, frozen=True):
    """Alert raised when a RAG Triad metric drops below threshold.

    Attributes:
        alert_type: Type of quality issue (e.g. ``"low_faithfulness"``).
        score: Observed score that triggered the alert.
        threshold: Threshold that was violated.
        query: The query that triggered the alert.
        message: Human-readable alert description.
    """

    alert_type: str
    score: float
    threshold: float
    query: str
    message: str


class RAGMonitorSummary(BaseModel, frozen=True):
    """Aggregated RAG quality summary over multiple queries.

    Attributes:
        total_queries: Number of queries evaluated.
        avg_context_relevance: Mean context relevance score.
        avg_faithfulness: Mean faithfulness score.
        avg_answer_relevance: Mean answer relevance score.
        alerts_triggered: Count of alerts raised during evaluation.
    """

    total_queries: int
    avg_context_relevance: float
    avg_faithfulness: float
    avg_answer_relevance: float
    alerts_triggered: int


# ── Evaluation functions ───────────────────────────────────────────────


def evaluate_rag_triad(
    score: RAGTriadScore,
    *,
    faithfulness_threshold: float = 0.85,
) -> RAGTriadAlert | None:
    """Evaluate a single RAG Triad score for faithfulness violations.

    Args:
        score: The RAG Triad evaluation to check.
        faithfulness_threshold: Minimum acceptable faithfulness score (default 0.85).

    Returns:
        A :class:`RAGTriadAlert` if faithfulness is below threshold, else ``None``.
    """
    if score.faithfulness < faithfulness_threshold:
        alert = RAGTriadAlert(
            alert_type="low_faithfulness",
            score=score.faithfulness,
            threshold=faithfulness_threshold,
            query=score.query,
            message=(
                f"Faithfulness score {score.faithfulness:.3f} below threshold "
                f"{faithfulness_threshold:.3f} for query: {score.query!r}"
            ),
        )
        logger.warning(
            "rag_faithfulness_alert",
            faithfulness=score.faithfulness,
            threshold=faithfulness_threshold,
            query=score.query,
            retrieved_count=score.retrieved_count,
        )
        return alert

    return None


def summarize_rag_metrics(
    scores: list[RAGTriadScore],
    *,
    faithfulness_threshold: float = 0.85,
) -> RAGMonitorSummary:
    """Compute aggregate RAG quality metrics over a list of evaluations.

    Args:
        scores: List of individual RAG Triad evaluations.
        faithfulness_threshold: Threshold passed to :func:`evaluate_rag_triad`
            for alert counting.

    Returns:
        A frozen :class:`RAGMonitorSummary` with averages and alert count.
    """
    total = len(scores)

    if total == 0:
        logger.warning("rag_summary_empty_scores")
        return RAGMonitorSummary(
            total_queries=0,
            avg_context_relevance=0.0,
            avg_faithfulness=0.0,
            avg_answer_relevance=0.0,
            alerts_triggered=0,
        )

    alerts_triggered = sum(
        1
        for s in scores
        if evaluate_rag_triad(s, faithfulness_threshold=faithfulness_threshold) is not None
    )

    avg_context_relevance = sum(s.context_relevance for s in scores) / total
    avg_faithfulness = sum(s.faithfulness for s in scores) / total
    avg_answer_relevance = sum(s.answer_relevance for s in scores) / total

    logger.info(
        "rag_metrics_summarized",
        total_queries=total,
        avg_context_relevance=round(avg_context_relevance, 4),
        avg_faithfulness=round(avg_faithfulness, 4),
        avg_answer_relevance=round(avg_answer_relevance, 4),
        alerts_triggered=alerts_triggered,
    )

    return RAGMonitorSummary(
        total_queries=total,
        avg_context_relevance=avg_context_relevance,
        avg_faithfulness=avg_faithfulness,
        avg_answer_relevance=avg_answer_relevance,
        alerts_triggered=alerts_triggered,
    )

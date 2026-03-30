"""Memory-specific configuration (FR-MEM-004/005/007)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MemorySettings:
    """Configuration for the memory layer.

    Constructed from the global ``Settings`` via :meth:`from_env` or
    directly in tests.
    """

    # ── Compaction (FR-MEM-005) ──────────────────────────────────────
    compaction_threshold: float = 0.70
    compaction_method: str = "verbatim"

    # ── RAG pipeline (FR-MEM-007) ────────────────────────────────────
    rag_chunk_size: int = 512
    rag_chunk_overlap_pct: float = 0.15
    rag_retrieval_k: int = 60
    rag_rerank_candidates: int = 50
    rag_rerank_top_n: int = 5
    rag_faithfulness_threshold: float = 0.85

    # ── Conversation history (FR-MEM-010) ────────────────────────────
    history_recent_count: int = 10

    # ── Decay (FR-MEM-012) ───────────────────────────────────────────
    decay_enabled: bool = False
    decay_default_half_life_hours: int = 720  # 30 days

    # ── Knowledge graph feature flag ─────────────────────────────────
    knowledge_graph_enabled: bool = True

    # ── External keys ────────────────────────────────────────────────
    cohere_api_key: str = ""

    # ── Cold storage ─────────────────────────────────────────────────
    cold_storage_endpoint: str = ""
    cold_storage_bucket: str = "colette-cold"

    # ── Database / backends ──────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://colette:colette@localhost:5432/colette"
    embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 1536

    @classmethod
    def from_env(cls, settings: object) -> MemorySettings:
        """Build from the global Settings instance.

        Reads matching attributes from *settings* with safe fallbacks.
        """

        def _get(attr: str, default: object) -> Any:
            return getattr(settings, attr, default)

        return cls(
            compaction_threshold=float(_get("compaction_threshold", 0.70)),
            rag_chunk_size=int(_get("rag_chunk_size", 512)),
            rag_faithfulness_threshold=float(_get("rag_faithfulness_threshold", 0.85)),
            knowledge_graph_enabled=bool(_get("knowledge_graph_enabled", True)),
            cohere_api_key=str(_get("cohere_api_key", "")),
            cold_storage_endpoint=str(_get("cold_storage_endpoint", "")),
            cold_storage_bucket=str(_get("cold_storage_bucket", "colette-cold")),
            decay_enabled=bool(_get("memory_decay_enabled", False)),
            database_url=str(_get("database_url", cls.database_url)),
            embedding_model=str(_get("embedding_model", cls.embedding_model)),
            embedding_dimensions=int(_get("embedding_dimensions", cls.embedding_dimensions)),
        )

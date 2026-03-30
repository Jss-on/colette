"""pgvector chunk indexer (FR-MEM-007).

Manages the ``chunks`` table in PostgreSQL with pgvector for
dense vector similarity search.
"""

from __future__ import annotations

from typing import Any

import structlog

from colette.memory.config import MemorySettings
from colette.memory.exceptions import MemoryBackendError
from colette.memory.models import ChunkRecord, RetrievalResult

logger = structlog.get_logger(__name__)

# Embedding batch size for API calls
_EMBED_BATCH_SIZE = 100


class PgVectorIndexer:
    """pgvector-backed chunk index implementing ChunkIndexer protocol.

    Uses SQLAlchemy async engine with the pgvector extension for
    dense vector storage and cosine similarity search.
    """

    def __init__(self, settings: MemorySettings) -> None:
        self._settings = settings
        self._engine: Any = None

    async def _ensure_engine(self) -> Any:
        if self._engine is None:
            try:
                from sqlalchemy.ext.asyncio import create_async_engine

                self._engine = create_async_engine(
                    self._settings.database_url,
                    pool_size=5,
                    max_overflow=10,
                )
            except Exception as exc:
                raise MemoryBackendError("pgvector", str(exc)) from exc
        return self._engine

    async def ensure_table(self) -> None:
        """Create the chunks table and pgvector index if they don't exist."""
        engine = await self._ensure_engine()
        dims = self._settings.embedding_dimensions
        async with engine.begin() as conn:
            await conn.execute(
                __import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS vector")
            )
            await conn.execute(
                __import__("sqlalchemy").text(f"""
                    CREATE TABLE IF NOT EXISTS chunks (
                        id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        source_path TEXT NOT NULL,
                        content TEXT NOT NULL,
                        chunk_index INTEGER NOT NULL,
                        total_chunks INTEGER NOT NULL,
                        token_count INTEGER NOT NULL,
                        embedding vector({dims}) NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
            )
            await conn.execute(
                __import__("sqlalchemy").text(
                    "CREATE INDEX IF NOT EXISTS ix_chunks_project ON chunks(project_id)"
                )
            )
            await conn.execute(
                __import__("sqlalchemy").text(
                    "CREATE INDEX IF NOT EXISTS ix_chunks_source ON chunks(source_path)"
                )
            )
        logger.info("pgvector_table_ensured")

    async def index_chunks(self, chunks: list[ChunkRecord]) -> int:
        """Index chunks with embeddings. Returns count inserted."""
        if not chunks:
            return 0

        engine = await self._ensure_engine()
        sa = __import__("sqlalchemy")
        inserted = 0

        # Generate embeddings in batches
        for batch_start in range(0, len(chunks), _EMBED_BATCH_SIZE):
            batch = chunks[batch_start : batch_start + _EMBED_BATCH_SIZE]
            embeddings = await self._generate_embeddings([c.content for c in batch])

            async with engine.begin() as conn:
                for chunk, embedding in zip(batch, embeddings, strict=True):
                    await conn.execute(
                        sa.text(
                            "INSERT INTO chunks "
                            "(id, project_id, source_path, content, "
                            "chunk_index, total_chunks, token_count, embedding) "
                            "VALUES (:id, :project_id, :source_path, :content, "
                            ":chunk_index, :total_chunks, :token_count, :embedding) "
                            "ON CONFLICT (id) DO NOTHING"
                        ),
                        {
                            "id": chunk.id,
                            "project_id": chunk.project_id,
                            "source_path": chunk.source_path,
                            "content": chunk.content,
                            "chunk_index": chunk.chunk_index,
                            "total_chunks": chunk.total_chunks,
                            "token_count": chunk.token_count,
                            "embedding": str(list(embedding)),
                        },
                    )
                    inserted += 1

        logger.info("chunks_indexed", count=inserted)
        return inserted

    async def delete_by_source(self, source_path: str) -> int:
        """Delete all chunks for a source path. Returns count deleted."""
        engine = await self._ensure_engine()
        sa = __import__("sqlalchemy")
        async with engine.begin() as conn:
            result = await conn.execute(
                sa.text("DELETE FROM chunks WHERE source_path = :path"),
                {"path": source_path},
            )
            count: int = int(result.rowcount)
        logger.info("chunks_deleted", source_path=source_path, count=count)
        return count

    async def search_dense(
        self,
        project_id: str,
        query_embedding: list[float],
        top_k: int = 60,
    ) -> list[RetrievalResult]:
        """Cosine similarity search against pgvector."""
        engine = await self._ensure_engine()
        sa = __import__("sqlalchemy")
        async with engine.connect() as conn:
            result = await conn.execute(
                sa.text(
                    "SELECT id, project_id, source_path, content, "
                    "chunk_index, total_chunks, token_count, "
                    "1 - (embedding <=> :query) AS score "
                    "FROM chunks "
                    "WHERE project_id = :project_id "
                    "ORDER BY embedding <=> :query "
                    "LIMIT :top_k"
                ),
                {
                    "query": str(query_embedding),
                    "project_id": project_id,
                    "top_k": top_k,
                },
            )
            rows = result.fetchall()

        return [
            RetrievalResult(
                chunk=ChunkRecord(
                    id=row[0],
                    project_id=row[1],
                    source_path=row[2],
                    content=row[3],
                    token_count=row[6],
                    chunk_index=row[4],
                    total_chunks=row[5],
                ),
                score=float(row[7]),
                source="dense",
            )
            for row in rows
        ]

    async def _generate_embeddings(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """Generate embeddings via LiteLLM."""
        try:
            import litellm

            response = await litellm.aembedding(
                model=self._settings.embedding_model,
                input=texts,
            )
            return [item["embedding"] for item in response.data]
        except Exception as exc:
            raise MemoryBackendError("embedding", str(exc)) from exc

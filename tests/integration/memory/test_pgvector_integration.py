"""Integration tests for pgvector indexer (requires PostgreSQL + pgvector).

Run with: pytest -m integration tests/integration/memory/
Requires: docker-compose up (postgres with pgvector extension)
"""

from __future__ import annotations

import pytest

from colette.memory.config import MemorySettings
from colette.memory.rag.indexer import PgVectorIndexer

pytestmark = [pytest.mark.integration, pytest.mark.slow]


@pytest.fixture
def indexer() -> PgVectorIndexer:
    return PgVectorIndexer(MemorySettings())


class TestPgVectorIntegration:
    async def test_ensure_table(self, indexer: PgVectorIndexer) -> None:
        await indexer.ensure_table()

    async def test_search_empty_returns_empty(self, indexer: PgVectorIndexer) -> None:
        await indexer.ensure_table()
        results = await indexer.search_dense(
            "nonexistent-project",
            [0.0] * 1536,
            top_k=5,
        )
        assert results == []

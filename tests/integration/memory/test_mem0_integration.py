"""Integration tests for Mem0 project memory (requires PostgreSQL).

Run with: pytest -m integration tests/integration/memory/
Requires: docker-compose up (postgres)
"""

from __future__ import annotations

import pytest

from colette.memory.config import MemorySettings
from colette.memory.models import MemoryEntry, MemoryScope
from colette.memory.project_memory import Mem0ProjectMemoryStore

pytestmark = [pytest.mark.integration, pytest.mark.slow]


@pytest.fixture
def store() -> Mem0ProjectMemoryStore:
    return Mem0ProjectMemoryStore(MemorySettings())


class TestMem0Integration:
    async def test_store_and_retrieve_cycle(self, store: Mem0ProjectMemoryStore) -> None:
        entry = MemoryEntry(
            id="",
            project_id="integration-test",
            content="The system uses PostgreSQL as the primary database.",
            scope=MemoryScope.SHARED,
        )
        entry_id = await store.store(entry)
        assert entry_id

        results = await store.retrieve("integration-test", "database", scope=MemoryScope.SHARED)
        assert len(results) >= 1

    async def test_scope_isolation(self, store: Mem0ProjectMemoryStore) -> None:
        entry = MemoryEntry(
            id="",
            project_id="scope-test",
            content="Private implementation detail.",
            scope=MemoryScope.PRIVATE,
            agent_id="agent-1",
        )
        await store.store(entry)

        results = await store.search(
            "scope-test",
            "implementation",
            scope=MemoryScope.SHARED,
        )
        private_results = [r for r in results if r.scope == MemoryScope.PRIVATE]
        assert len(private_results) == 0

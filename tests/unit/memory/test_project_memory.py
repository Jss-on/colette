"""Tests for Mem0 project memory store (FR-MEM-001/003/012)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from colette.memory.config import MemorySettings
from colette.memory.exceptions import MemoryBackendError, ScopeViolationError
from colette.memory.models import MemoryEntry, MemoryScope
from colette.memory.project_memory import Mem0ProjectMemoryStore


@pytest.fixture
def mem_settings() -> MemorySettings:
    return MemorySettings(decay_enabled=True, decay_default_half_life_hours=24)


@pytest.fixture
def mock_mem0_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def store(
    mem_settings: MemorySettings,
    mock_mem0_client: MagicMock,
) -> Mem0ProjectMemoryStore:
    s = Mem0ProjectMemoryStore(mem_settings)
    s._client = mock_mem0_client
    return s


class TestScopeEnforcement:
    def test_private_cannot_access_shared(self) -> None:
        with pytest.raises(ScopeViolationError):
            Mem0ProjectMemoryStore._check_scope(MemoryScope.PRIVATE, MemoryScope.SHARED)

    def test_private_cannot_access_global(self) -> None:
        with pytest.raises(ScopeViolationError):
            Mem0ProjectMemoryStore._check_scope(MemoryScope.PRIVATE, MemoryScope.GLOBAL)

    def test_shared_cannot_access_private(self) -> None:
        with pytest.raises(ScopeViolationError):
            Mem0ProjectMemoryStore._check_scope(MemoryScope.SHARED, MemoryScope.PRIVATE)

    def test_shared_can_access_shared(self) -> None:
        Mem0ProjectMemoryStore._check_scope(MemoryScope.SHARED, MemoryScope.SHARED)

    def test_global_can_access_all(self) -> None:
        Mem0ProjectMemoryStore._check_scope(MemoryScope.GLOBAL, MemoryScope.GLOBAL)
        Mem0ProjectMemoryStore._check_scope(MemoryScope.GLOBAL, MemoryScope.SHARED)
        Mem0ProjectMemoryStore._check_scope(MemoryScope.GLOBAL, MemoryScope.PRIVATE)


class TestStore:
    async def test_store_returns_id(
        self,
        store: Mem0ProjectMemoryStore,
        mock_mem0_client: MagicMock,
    ) -> None:
        mock_mem0_client.add.return_value = {"id": "new-id"}
        entry = MemoryEntry(id="", project_id="proj-1", content="fact: sky is blue")
        result = await store.store(entry)
        assert result == "new-id"
        mock_mem0_client.add.assert_called_once()

    async def test_store_wraps_exception(
        self,
        store: Mem0ProjectMemoryStore,
        mock_mem0_client: MagicMock,
    ) -> None:
        mock_mem0_client.add.side_effect = RuntimeError("connection lost")
        entry = MemoryEntry(id="x", project_id="proj-1", content="data")
        with pytest.raises(MemoryBackendError, match="mem0"):
            await store.store(entry)


class TestUpdate:
    async def test_update_calls_client(
        self,
        store: Mem0ProjectMemoryStore,
        mock_mem0_client: MagicMock,
    ) -> None:
        result = await store.update("mem-1", "updated content")
        mock_mem0_client.update.assert_called_once_with(
            "mem-1", data="updated content", metadata=None
        )
        assert result.content == "updated content"

    async def test_update_wraps_exception(
        self,
        store: Mem0ProjectMemoryStore,
        mock_mem0_client: MagicMock,
    ) -> None:
        mock_mem0_client.update.side_effect = RuntimeError("fail")
        with pytest.raises(MemoryBackendError):
            await store.update("mem-1", "data")


class TestDelete:
    async def test_delete_calls_client(
        self,
        store: Mem0ProjectMemoryStore,
        mock_mem0_client: MagicMock,
    ) -> None:
        await store.delete("mem-1")
        mock_mem0_client.delete.assert_called_once_with("mem-1")


class TestSearch:
    async def test_search_filters_by_scope(
        self,
        store: Mem0ProjectMemoryStore,
        mock_mem0_client: MagicMock,
    ) -> None:
        mock_mem0_client.search.return_value = [
            {"id": "1", "memory": "fact A", "metadata": {"scope": "shared"}},
            {"id": "2", "memory": "fact B", "metadata": {"scope": "private"}},
        ]
        results = await store.search("proj-1", "test", scope=MemoryScope.SHARED)
        assert len(results) == 1
        assert results[0].id == "1"

    async def test_search_scope_violation(
        self,
        store: Mem0ProjectMemoryStore,
    ) -> None:
        with pytest.raises(ScopeViolationError):
            await store.search(
                "proj-1",
                "test",
                scope=MemoryScope.PRIVATE,
                agent_scope=MemoryScope.SHARED,
            )


class TestDecay:
    async def test_decay_disabled_returns_zero(self) -> None:
        settings = MemorySettings(decay_enabled=False)
        s = Mem0ProjectMemoryStore(settings)
        result = await s.apply_decay("proj-1", datetime.now(UTC))
        assert result == 0

    async def test_decay_skips_permanent(
        self,
        store: Mem0ProjectMemoryStore,
        mock_mem0_client: MagicMock,
    ) -> None:
        mock_mem0_client.search.return_value = [
            {
                "id": "perm",
                "memory": "critical decision",
                "metadata": {
                    "scope": "global",
                    "is_permanent": "True",
                    "confidence": "1.0",
                },
            },
        ]
        count = await store.apply_decay("proj-1", datetime.now(UTC))
        assert count == 0
        mock_mem0_client.delete.assert_not_called()

    async def test_decay_deletes_old_memories(
        self,
        store: Mem0ProjectMemoryStore,
        mock_mem0_client: MagicMock,
    ) -> None:
        mock_mem0_client.search.return_value = [
            {
                "id": "old-1",
                "memory": "stale fact",
                "metadata": {
                    "scope": "global",
                    "is_permanent": "False",
                    "confidence": "1.0",
                },
            },
        ]
        # The entry's updated_at defaults to now(), but the decay logic
        # uses MemoryEntry.updated_at which defaults to now(). We test
        # the path by providing a far-future current_time.
        far_future = datetime.now(UTC) + timedelta(days=365)
        count = await store.apply_decay("proj-1", far_future)
        assert count == 1
        mock_mem0_client.delete.assert_called_once_with("old-1")

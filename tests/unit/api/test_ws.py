"""Tests for WebSocket connection manager."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from colette.api.routes.ws import ConnectionManager


class TestConnectionManager:
    @pytest.mark.asyncio
    async def test_connect_accepts_websocket(self) -> None:
        mgr = ConnectionManager()
        ws = AsyncMock()
        await mgr.connect("proj-1", ws)
        ws.accept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_tracks_connection(self) -> None:
        mgr = ConnectionManager()
        ws = AsyncMock()
        await mgr.connect("proj-1", ws)
        assert ws in mgr._connections["proj-1"]

    def test_disconnect_removes_connection(self) -> None:
        mgr = ConnectionManager()
        ws = MagicMock()
        mgr._connections["proj-1"].append(ws)
        mgr.disconnect("proj-1", ws)
        assert ws not in mgr._connections.get("proj-1", [])

    def test_disconnect_cleans_up_empty_project(self) -> None:
        mgr = ConnectionManager()
        ws = MagicMock()
        mgr._connections["proj-1"].append(ws)
        mgr.disconnect("proj-1", ws)
        assert "proj-1" not in mgr._connections

    def test_disconnect_unknown_is_safe(self) -> None:
        mgr = ConnectionManager()
        ws = MagicMock()
        mgr.disconnect("proj-unknown", ws)  # Should not raise

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all(self) -> None:
        mgr = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        mgr._connections["proj-1"].extend([ws1, ws2])

        await mgr.broadcast("proj-1", {"event": "progress"})
        ws1.send_json.assert_awaited_once_with({"event": "progress"})
        ws2.send_json.assert_awaited_once_with({"event": "progress"})

    @pytest.mark.asyncio
    async def test_broadcast_removes_failed_connections(self) -> None:
        mgr = ConnectionManager()
        good_ws = AsyncMock()
        bad_ws = AsyncMock()
        bad_ws.send_json.side_effect = Exception("connection closed")
        mgr._connections["proj-1"].extend([good_ws, bad_ws])

        await mgr.broadcast("proj-1", {"event": "test"})
        good_ws.send_json.assert_awaited_once()
        assert bad_ws not in mgr._connections.get("proj-1", [])

    @pytest.mark.asyncio
    async def test_broadcast_no_connections_is_noop(self) -> None:
        mgr = ConnectionManager()
        await mgr.broadcast("proj-unknown", {"event": "test"})

    @pytest.mark.asyncio
    async def test_multiple_projects_isolated(self) -> None:
        mgr = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await mgr.connect("proj-1", ws1)
        await mgr.connect("proj-2", ws2)

        await mgr.broadcast("proj-1", {"event": "p1"})
        ws1.send_json.assert_awaited_once_with({"event": "p1"})
        ws2.send_json.assert_not_awaited()

"""WebSocket endpoint for real-time pipeline updates (NFR-USA-003)."""

from __future__ import annotations

import asyncio
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from colette.api.deps import get_pipeline_runner, get_settings

router = APIRouter()


class ConnectionManager:
    """Tracks active WebSocket connections per project."""

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, project_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections[project_id].append(ws)

    def disconnect(self, project_id: str, ws: WebSocket) -> None:
        conns = self._connections.get(project_id, [])
        if ws in conns:
            conns.remove(ws)
        if not conns:
            self._connections.pop(project_id, None)

    async def broadcast(self, project_id: str, data: dict) -> None:  # type: ignore[type-arg]
        for ws in list(self._connections.get(project_id, [])):
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(project_id, ws)


manager = ConnectionManager()


@router.websocket("/api/v1/projects/{project_id}/ws")
async def pipeline_ws(websocket: WebSocket, project_id: str) -> None:
    """WebSocket endpoint streaming pipeline progress events."""
    settings = get_settings()
    runner = get_pipeline_runner(settings)

    await manager.connect(project_id, websocket)
    try:
        last_stage = ""
        while True:
            if not runner.is_active(project_id):
                await websocket.send_json({"event": "complete", "project_id": project_id})
                break

            try:
                progress = await runner.get_progress(project_id)
                event_data = {
                    "event": "progress",
                    "project_id": progress.project_id,
                    "stage": progress.stage,
                    "status": progress.status,
                    "elapsed_seconds": progress.elapsed_seconds,
                    "tokens_used": progress.tokens_used,
                    "timestamp": progress.timestamp.isoformat(),
                }
                if progress.stage != last_stage:
                    last_stage = progress.stage
                await websocket.send_json(event_data)
            except KeyError:
                await websocket.send_json({"event": "complete", "project_id": project_id})
                break

            await asyncio.sleep(settings.progress_stream_interval_seconds)
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(project_id, websocket)

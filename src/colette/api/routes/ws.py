"""WebSocket endpoint for real-time pipeline updates (NFR-USA-003).

Event-driven streaming via the pipeline event bus — replaces the
original polling implementation.  Supports catch-up events for
reconnection and heartbeat pings for connection health.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from colette.api.deps import get_pipeline_runner, get_settings
from colette.orchestrator.event_bus import EventType

router = APIRouter()

_TERMINAL_EVENTS = frozenset({EventType.PIPELINE_COMPLETED, EventType.PIPELINE_FAILED})


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

    async def broadcast(self, project_id: str, data: dict[str, Any]) -> None:
        for ws in list(self._connections.get(project_id, [])):
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(project_id, ws)


manager = ConnectionManager()


def _event_to_dict(event: object) -> dict[str, Any]:
    """Convert a PipelineEvent to a JSON-serialisable dict."""
    from colette.orchestrator.event_bus import PipelineEvent

    if not isinstance(event, PipelineEvent):
        return {}
    return {
        "event_type": event.event_type.value,
        "project_id": event.project_id,
        "stage": event.stage,
        "agent": event.agent,
        "model": event.model,
        "message": event.message,
        "detail": dict(event.detail),
        "timestamp": event.timestamp.isoformat(),
        "elapsed_seconds": event.elapsed_seconds,
        "tokens_used": event.tokens_used,
    }


async def _emit_ws_catchup(
    websocket: WebSocket,
    project_id: str,
    runner: object,
) -> None:
    """Send synthetic catch-up events for stages that already progressed."""
    from colette.orchestrator.runner import PipelineRunner
    from colette.orchestrator.state import STAGE_ORDER

    if not isinstance(runner, PipelineRunner):
        return
    try:
        progress = await runner.get_progress(project_id)
    except Exception:
        return
    try:
        current_idx = STAGE_ORDER.index(progress.stage)
    except ValueError:
        return

    ts = datetime.now(UTC).isoformat()
    for i, stage_name in enumerate(STAGE_ORDER):
        if i < current_idx:
            await websocket.send_json(
                {
                    "event_type": "stage_started",
                    "project_id": project_id,
                    "stage": stage_name,
                    "timestamp": ts,
                }
            )
            await websocket.send_json(
                {
                    "event_type": "stage_completed",
                    "project_id": project_id,
                    "stage": stage_name,
                    "timestamp": ts,
                    "elapsed_seconds": progress.elapsed_seconds,
                }
            )
        elif i == current_idx:
            await websocket.send_json(
                {
                    "event_type": "stage_started",
                    "project_id": project_id,
                    "stage": stage_name,
                    "timestamp": ts,
                }
            )


@router.websocket("/projects/{project_id}/ws")
async def pipeline_ws(websocket: WebSocket, project_id: str) -> None:
    """WebSocket endpoint streaming pipeline events in real-time.

    Subscribes to the event bus and forwards all events — including
    ``AGENT_STREAM_CHUNK`` for live LLM output — as JSON frames.
    """
    settings = get_settings()
    runner = get_pipeline_runner(settings)
    heartbeat = settings.sse_heartbeat_seconds

    await manager.connect(project_id, websocket)

    # If pipeline already finished, send terminal event and close.
    if not runner.is_active(project_id):
        await websocket.send_json(
            {
                "event_type": "complete",
                "project_id": project_id,
            }
        )
        manager.disconnect(project_id, websocket)
        return

    # Subscribe to event bus FIRST, then send catch-up.
    queue = runner.event_bus.subscribe(project_id)
    try:
        await _emit_ws_catchup(websocket, project_id, runner)

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=heartbeat)
            except TimeoutError:
                # Heartbeat ping to keep connection alive.
                await websocket.send_json({"event_type": "heartbeat"})
                if not runner.is_active(project_id):
                    await websocket.send_json(
                        {
                            "event_type": "complete",
                            "project_id": project_id,
                        }
                    )
                    break
                continue

            payload = _event_to_dict(event)
            await websocket.send_json(payload)

            if event.event_type in _TERMINAL_EVENTS:
                break

    except WebSocketDisconnect:
        pass
    except Exception:
        import structlog

        structlog.get_logger(__name__).warning("ws.unexpected_error", project_id=project_id)
    finally:
        runner.event_bus.unsubscribe(project_id, queue)
        manager.disconnect(project_id, websocket)

from __future__ import annotations

from collections import defaultdict

from fastapi import WebSocket

from app.core.logging import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """Tracks live WebSocket connections per user so the backend can push
    notifications (or voice audio) without the client polling."""

    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[user_id].append(websocket)

    def register(self, user_id: str, websocket: WebSocket) -> None:
        """Register an already-accepted WebSocket (auth-first protocol)."""
        self._connections[user_id].append(websocket)

    def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        if websocket in self._connections.get(user_id, []):
            self._connections[user_id].remove(websocket)
        if not self._connections.get(user_id):
            self._connections.pop(user_id, None)

    async def send_json_to_user(self, user_id: str, payload: dict) -> None:
        for ws in list(self._connections.get(user_id, [])):
            try:
                await ws.send_json(payload)
            except Exception as exc:
                logger.warning("ws_send_failed", user_id=user_id, error=str(exc))
                self.disconnect(user_id, ws)

    def is_connected(self, user_id: str) -> bool:
        return bool(self._connections.get(user_id))


notification_manager = ConnectionManager()
voice_manager = ConnectionManager()

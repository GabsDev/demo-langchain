"""WebSocket connection manager for the Kitchen Display System.

Broadcasts `order.created` and `order.updated` events to every connected
dashboard. Multiple screens stay in sync.
"""
from __future__ import annotations

import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)
        client = websocket.client.host if websocket.client else "unknown"
        logger.info(
            "WebSocket client connected from %s (%d total)", client, self.connection_count
        )

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)
        logger.info("WebSocket client disconnected (%d total)", self.connection_count)

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def broadcast(self, message: dict) -> None:
        targets = list(self._connections)
        logger.debug(
            "Broadcast %s to %d client(s)", message.get("type"), len(targets)
        )
        dead: list[WebSocket] = []
        for websocket in targets:
            try:
                await websocket.send_json(message)
            except Exception:
                logger.debug("Dropping dead WebSocket connection", exc_info=True)
                dead.append(websocket)
        for websocket in dead:
            self.disconnect(websocket)

    async def broadcast_order(self, order, event: str) -> None:
        """Broadcast an order serialized as an `order.created`/`order.updated` event."""
        await self.broadcast({"type": event, "order": order.to_dict()})
        logger.info(
            "Broadcast %s for order %s to %d client(s)",
            event, order.id, self.connection_count,
        )


manager = ConnectionManager()

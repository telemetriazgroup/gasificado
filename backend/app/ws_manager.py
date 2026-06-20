import asyncio
import json
from datetime import datetime
from typing import Any


class ConnectionManager:
    def __init__(self):
        self.active: list[Any] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket):
        await websocket.accept()
        async with self._lock:
            self.active.append(websocket)

    async def disconnect(self, websocket):
        async with self._lock:
            if websocket in self.active:
                self.active.remove(websocket)

    async def broadcast(self, event_type: str, payload: dict):
        message = json.dumps(
            {
                "type": event_type,
                "payload": payload,
                "timestamp": datetime.utcnow().isoformat(),
            },
            default=str,
        )
        dead = []
        async with self._lock:
            clients = list(self.active)
        for ws in clients:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)


terminal_manager = ConnectionManager()

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.ws_manager import terminal_manager

router = APIRouter(tags=["terminal"])


@router.websocket("/ws/terminal")
async def terminal_ws(websocket: WebSocket):
    await terminal_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await terminal_manager.disconnect(websocket)

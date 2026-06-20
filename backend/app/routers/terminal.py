from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.auth import decode_token
from app.ws_manager import realtime_manager, terminal_manager

router = APIRouter(tags=["terminal"])


def _validate_ws_token(websocket: WebSocket, required_role: str | None = None):
    token = websocket.query_params.get("token")
    if not token:
        return None
    try:
        user = decode_token(token)
    except Exception:
        return None
    if required_role and user.role != required_role:
        return None
    return user


@router.websocket("/ws/terminal")
async def terminal_ws(websocket: WebSocket):
    user = _validate_ws_token(websocket, required_role="admin")
    if not user:
        await websocket.close(code=4401)
        return
    await terminal_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await terminal_manager.disconnect(websocket)


@router.websocket("/ws/realtime")
async def realtime_ws(websocket: WebSocket):
    user = _validate_ws_token(websocket)
    if not user:
        await websocket.close(code=4401)
        return
    await realtime_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await realtime_manager.disconnect(websocket)

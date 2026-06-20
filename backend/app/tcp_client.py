import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Device


async def ensure_device_on_bridge(db: Session, imei: str) -> None:
    """Verifica sesión TCP real en tcp_bridge y sincroniza estado en BD."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"{settings.tcp_bridge_url}/internal/can_send",
                params={"imei": imei},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"No se pudo contactar al puente TCP: {exc}",
        ) from exc

    if not data.get("ready"):
        device = db.query(Device).filter(Device.imei == imei).first()
        if device:
            device.is_connected = False
            db.commit()
        sessions = data.get("active_sessions", 0)
        raise HTTPException(
            status_code=409,
            detail=(
                f"Dispositivo {imei} no conectado al puente TCP "
                f"(sesiones activas: {sessions}). "
                "Espere a que el equipo envíe datos o reconecte."
            ),
        )


async def post_tcp_command(imei: str, command: str, append_newline: bool = True) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{settings.tcp_bridge_url}/internal/send",
                json={
                    "imei": imei,
                    "command": command,
                    "append_newline": append_newline,
                },
            )
            if resp.status_code >= 400:
                detail = resp.text
                try:
                    detail = resp.json().get("detail", detail)
                except Exception:
                    pass
                raise HTTPException(status_code=resp.status_code, detail=detail)
            return resp.json()
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Error enviando comando: {exc}") from exc

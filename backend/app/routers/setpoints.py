from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.auth import User, require_client_or_admin
from app.database import get_db
from app.models import Device, SetPoint
from app.schemas import SetPointOut, SetPointRequest
from app.tcp_client import ensure_device_on_bridge, post_tcp_command
from app.timezone_util import from_utc_naive, now_utc_naive

router = APIRouter(prefix="/api/setpoints", tags=["setpoints"])


@router.get("", response_model=SetPointOut | None)
def get_setpoint(
    imei: str = Query(...),
    db: Session = Depends(get_db),
    _user: User = Depends(require_client_or_admin),
):
    row = db.query(SetPoint).filter(SetPoint.imei == imei).order_by(desc(SetPoint.updated_at)).first()
    if not row:
        return None
    return SetPointOut(
        imei=row.imei,
        temperature=row.temperature,
        gas_ppm=row.gas_ppm,
        updated_by=row.updated_by,
        updated_at=from_utc_naive(row.updated_at),
        applied=row.applied,
    )


@router.post("", response_model=SetPointOut)
async def save_setpoint(
    body: SetPointRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_client_or_admin),
):
    device = db.query(Device).filter(Device.imei == body.imei).first()
    if not device:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")

    temp_int = int(round(body.temperature * 10))
    command = f"SETPOINT,{temp_int},{body.gas_ppm}"
    applied = False

    if body.apply_to_device:
        try:
            await ensure_device_on_bridge(db, body.imei)
            result = await post_tcp_command(body.imei, command, True)
            applied = result.get("success", False)
        except HTTPException:
            applied = False

    row = SetPoint(
        imei=body.imei,
        temperature=body.temperature,
        gas_ppm=body.gas_ppm,
        updated_by=user.username,
        updated_at=now_utc_naive(),
        applied=applied,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return SetPointOut(
        imei=row.imei,
        temperature=row.temperature,
        gas_ppm=row.gas_ppm,
        updated_by=row.updated_by,
        updated_at=from_utc_naive(row.updated_at),
        applied=row.applied,
    )

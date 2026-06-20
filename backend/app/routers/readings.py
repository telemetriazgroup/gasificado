from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CommandLog, Device, Reading
from app.schemas import ChartData, ChartPoint, CommandRequest, CommandResponse, LatestData, ReadingOut
from app.config import settings
import httpx

router = APIRouter(prefix="/api", tags=["readings"])


@router.get("/devices")
def list_devices(db: Session = Depends(get_db)):
    devices = db.query(Device).order_by(desc(Device.last_seen_at)).all()
    return [
        {
            "imei": d.imei,
            "last_ip": d.last_ip,
            "last_seen_at": d.last_seen_at,
            "is_connected": d.is_connected,
        }
        for d in devices
    ]


@router.get("/latest", response_model=LatestData)
def get_latest(imei: str | None = Query(None), db: Session = Depends(get_db)):
    device_q = db.query(Device)
    if imei:
        device_q = device_q.filter(Device.imei == imei)
    device = device_q.order_by(desc(Device.last_seen_at)).first()

    reading_q = db.query(Reading).filter(Reading.message_type == "sensor")
    if imei:
        reading_q = reading_q.filter(Reading.imei == imei)
    elif device:
        reading_q = reading_q.filter(Reading.imei == device.imei)
    latest_reading = reading_q.order_by(desc(Reading.received_at)).first()

    last_cmd = None
    target_imei = imei or (device.imei if device else None)
    if target_imei:
        cmd = (
            db.query(CommandLog)
            .filter(CommandLog.imei == target_imei)
            .order_by(desc(CommandLog.sent_at))
            .first()
        )
        if cmd:
            last_cmd = {
                "command": cmd.command,
                "status": cmd.status,
                "sent_at": cmd.sent_at,
                "ack_at": cmd.ack_at,
            }

    return LatestData(
        device=device,
        latest_reading=latest_reading,
        last_command=last_cmd,
    )


@router.get("/readings", response_model=list[ReadingOut])
def get_readings(
    imei: str | None = Query(None),
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    message_type: str | None = Query(None),
    limit: int = Query(500, le=5000),
    db: Session = Depends(get_db),
):
    q = db.query(Reading)
    if imei:
        q = q.filter(Reading.imei == imei)
    if from_date:
        q = q.filter(Reading.received_at >= from_date)
    if to_date:
        q = q.filter(Reading.received_at <= to_date)
    if message_type:
        q = q.filter(Reading.message_type == message_type)
    return q.order_by(desc(Reading.received_at)).limit(limit).all()


@router.get("/chart", response_model=ChartData)
def get_chart_data(
    imei: str = Query(...),
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
):
    q = db.query(Reading).filter(Reading.imei == imei, Reading.message_type == "sensor")
    if from_date:
        q = q.filter(Reading.received_at >= from_date)
    if to_date:
        q = q.filter(Reading.received_at <= to_date)
    rows = q.order_by(Reading.received_at).all()
    return ChartData(
        imei=imei,
        points=[
            ChartPoint(
                timestamp=r.received_at,
                temperature=r.temperature,
                gas_ppm=r.gas_ppm,
            )
            for r in rows
        ],
    )


@router.post("/commands", response_model=CommandResponse)
async def send_command(body: CommandRequest, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.imei == body.imei).first()
    if not device or not device.is_connected:
        raise HTTPException(status_code=409, detail="Dispositivo no conectado")

    cmd_log = CommandLog(imei=body.imei, command=body.command, status="sent")
    db.add(cmd_log)
    db.commit()

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{settings.tcp_bridge_url}/internal/send",
                json={
                    "imei": body.imei,
                    "command": body.command,
                    "append_newline": body.append_newline,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        cmd_log.status = "error"
        db.commit()
        raise HTTPException(status_code=502, detail=f"Error enviando comando: {exc}")

    if not data.get("success"):
        cmd_log.status = "error"
        db.commit()
        raise HTTPException(status_code=502, detail=data.get("message", "Error desconocido"))

    return CommandResponse(success=True, message="Comando enviado", command=body.command)

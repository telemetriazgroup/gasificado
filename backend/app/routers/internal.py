from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.display_service import get_display_rules
from app.display_transform import apply_client_sensor_values
from app.models import CommandLog, Device, Reading, TerminalLog
from app.raw_logger import append_raw_log
from app.schemas import ConnectionStatusIn, TelemetryIn, TerminalIn
from app.timezone_util import now_utc_naive, parse_incoming_timestamp
from app.ws_manager import realtime_manager, terminal_manager

router = APIRouter(prefix="/api/internal", tags=["internal"])


def _upsert_device(db: Session, imei: str, ip: str | None, connected: bool = True):
    device = db.query(Device).filter(Device.imei == imei).first()
    now = now_utc_naive()
    if not device:
        device = Device(imei=imei, last_ip=ip, last_seen_at=now, is_connected=connected)
        db.add(device)
    else:
        device.last_ip = ip or device.last_ip
        device.last_seen_at = now
        device.is_connected = connected
    return device


@router.post("/disconnect_all")
def disconnect_all(db: Session = Depends(get_db)):
    db.query(Device).update({Device.is_connected: False})
    db.commit()
    return {"ok": True}


@router.post("/telemetry")
async def ingest_telemetry(body: TelemetryIn, db: Session = Depends(get_db)):
    ts = parse_incoming_timestamp(body.timestamp)
    append_raw_log(body.raw_message, source="tcp")

    if body.imei:
        _upsert_device(db, body.imei, body.ip)

    reading = Reading(
        imei=body.imei or "unknown",
        ip=body.ip,
        temperature=body.temperature,
        gas_ppm=body.gas_ppm,
        raw_message=body.raw_message,
        message_type=body.message_type,
        received_at=ts,
    )
    db.add(reading)

    if body.message_type == "command_ack" and body.imei:
        pending = (
            db.query(CommandLog)
            .filter(CommandLog.imei == body.imei, CommandLog.status == "sent")
            .order_by(CommandLog.sent_at.desc())
            .first()
        )
        if pending:
            pending.status = "acknowledged"
            pending.ack_at = ts
            pending.response = body.raw_message

    terminal = TerminalLog(
        imei=body.imei,
        direction="RX",
        message=body.raw_message,
        logged_at=ts,
    )
    db.add(terminal)
    db.commit()

    rules = get_display_rules(db)
    temp_client, gas_client = apply_client_sensor_values(
        body.temperature, body.gas_ppm, rules
    )

    admin_payload = {
        "imei": body.imei,
        "ip": body.ip,
        "temperature": body.temperature,
        "gas_ppm": body.gas_ppm,
        "raw_message": body.raw_message,
        "message_type": body.message_type,
    }
    client_payload = {
        **admin_payload,
        "temperature": temp_client,
        "gas_ppm": gas_client,
        "gas_display": gas_client,
        "temperature_display": temp_client,
    }

    await realtime_manager.broadcast("telemetry", client_payload)
    await terminal_manager.broadcast("telemetry", admin_payload)
    return {"ok": True}


@router.post("/terminal")
async def ingest_terminal(body: TerminalIn, db: Session = Depends(get_db)):
    ts = parse_incoming_timestamp(body.timestamp)
    append_raw_log(f"{body.direction}: {body.message}", source="terminal")
    entry = TerminalLog(
        imei=body.imei,
        direction=body.direction,
        message=body.message,
        logged_at=ts,
    )
    db.add(entry)
    db.commit()

    await terminal_manager.broadcast(
        "terminal",
        {
            "imei": body.imei,
            "direction": body.direction,
            "message": body.message,
        },
    )
    return {"ok": True}


@router.post("/connection")
async def update_connection(body: ConnectionStatusIn, db: Session = Depends(get_db)):
    device = _upsert_device(db, body.imei, body.ip, body.connected)
    if not body.connected:
        device.is_connected = False
    db.commit()
    msg = f"connection imei={body.imei} ip={body.ip} connected={body.connected}"
    append_raw_log(msg, source="tcp")

    payload = {
        "imei": body.imei,
        "ip": body.ip,
        "connected": body.connected,
    }
    await realtime_manager.broadcast("connection", payload)
    await terminal_manager.broadcast("connection", payload)
    return {"ok": True}

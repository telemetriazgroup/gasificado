from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.auth import User, require_admin
from app.database import get_db
from app.display_service import get_display_rules, save_display_rules
from app.display_transform import DisplayRules
from app.models import CommandLog, DisplayConfig, Reading
from app.raw_logger import list_log_files, read_log_file
from app.reading_mapper import build_reading_out, get_rules
from app.schemas import CommandAuditOut, DisplayConfigOut, DisplayConfigUpdate, ReadingOut
from app.timezone_util import from_utc_naive, parse_incoming_timestamp

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/display-config", response_model=DisplayConfigOut)
def get_config(db: Session = Depends(get_db), _user: User = Depends(require_admin)):
    rules = get_display_rules(db)
    row = db.query(DisplayConfig).filter(DisplayConfig.id == 1).first()
    return DisplayConfigOut(
        config=rules.to_dict(),
        updated_by=row.updated_by if row else "system",
        updated_at=from_utc_naive(row.updated_at) if row and row.updated_at else None,
    )


@router.put("/display-config", response_model=DisplayConfigOut)
def update_config(
    body: DisplayConfigUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    rules = DisplayRules.from_dict(body.config)
    save_display_rules(db, rules, user.username)
    row = db.query(DisplayConfig).filter(DisplayConfig.id == 1).first()
    return DisplayConfigOut(
        config=rules.to_dict(),
        updated_by=user.username,
        updated_at=from_utc_naive(row.updated_at) if row else None,
    )


@router.get("/readings/raw", response_model=list[ReadingOut])
def raw_readings_table(
    imei: str | None = Query(None),
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    limit: int = Query(500, le=5000),
    db: Session = Depends(get_db),
    _user: User = Depends(require_admin),
):
    q = db.query(Reading).filter(Reading.message_type == "sensor")
    if imei:
        q = q.filter(Reading.imei == imei)
    if from_date:
        q = q.filter(Reading.received_at >= parse_incoming_timestamp(from_date))
    if to_date:
        q = q.filter(Reading.received_at <= parse_incoming_timestamp(to_date))
    rows = q.order_by(desc(Reading.received_at)).limit(limit).all()
    rules = get_rules(db)
    return [build_reading_out(r, "admin", rules) for r in rows]


@router.get("/commands/audit", response_model=list[CommandAuditOut])
def commands_audit(
    imei: str | None = Query(None),
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    limit: int = Query(500, le=2000),
    db: Session = Depends(get_db),
    _user: User = Depends(require_admin),
):
    q = db.query(CommandLog)
    if imei:
        q = q.filter(CommandLog.imei == imei)
    if from_date:
        q = q.filter(CommandLog.sent_at >= parse_incoming_timestamp(from_date))
    if to_date:
        q = q.filter(CommandLog.sent_at <= parse_incoming_timestamp(to_date))
    rows = q.order_by(desc(CommandLog.sent_at)).limit(limit).all()
    return [
        CommandAuditOut(
            id=r.id,
            imei=r.imei,
            command=r.command,
            status=r.status,
            triggered_by=r.triggered_by,
            source=r.source,
            sent_at=from_utc_naive(r.sent_at),
            ack_at=from_utc_naive(r.ack_at) if r.ack_at else None,
            response=r.response,
        )
        for r in rows
    ]


@router.get("/logs/files")
def log_files(_user: User = Depends(require_admin)):
    return {"files": list_log_files()}


@router.get("/logs/content")
def log_content(
    filename: str = Query(...),
    tail: int = Query(500, le=5000),
    _user: User = Depends(require_admin),
):
    return {"filename": filename, "lines": read_log_file(filename, tail)}


@router.get("/logs/download")
def log_download(filename: str = Query(...), _user: User = Depends(require_admin)):
    lines = read_log_file(filename, 100000)
    if not lines and filename not in list_log_files():
        return PlainTextResponse("Archivo no encontrado", status_code=404)
    return PlainTextResponse("\n".join(lines), media_type="text/plain")

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/Bogota")


def now_local() -> datetime:
    """Hora actual en GMT-5 (America/Bogota)."""
    return datetime.now(LOCAL_TZ)


def to_utc_naive(dt: datetime | None) -> datetime | None:
    """Convierte datetime con o sin tz a UTC naive para PostgreSQL."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def from_utc_naive(dt: datetime | None) -> datetime | None:
    """Convierte UTC naive de BD a GMT-5 con tzinfo."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ)


def now_utc_naive() -> datetime:
    """Timestamp UTC naive para almacenar en BD."""
    return to_utc_naive(now_local())  # type: ignore[return-value]


def parse_incoming_timestamp(raw: datetime | str | None) -> datetime:
    """Normaliza timestamp entrante asumiendo GMT-5 si no trae zona."""
    if raw is None:
        return now_utc_naive()
    if isinstance(raw, str):
        raw = raw.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            return now_utc_naive()
    else:
        dt = raw
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return to_utc_naive(dt)  # type: ignore[return-value]

from datetime import datetime
from pathlib import Path

from app.timezone_util import from_utc_naive

LOG_DIR = Path("/app/logs")


def append_raw_log(message: str, source: str = "tcp") -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    now = from_utc_naive(datetime.utcnow())
    date_str = now.strftime("%d_%m_%Y")
    time_str = now.strftime("%H:%M:%S")
    path = LOG_DIR / f"raw_tcp_{date_str}.log"
    line = f"[{time_str}] [{source}] {message}\n"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)


def list_log_files() -> list[str]:
    if not LOG_DIR.exists():
        return []
    return sorted(
        [p.name for p in LOG_DIR.glob("raw_tcp_*.log")],
        reverse=True,
    )


def read_log_file(filename: str, tail: int = 500) -> list[str]:
    if ".." in filename or "/" in filename:
        return []
    path = LOG_DIR / filename
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return lines[-tail:]

import re
from datetime import datetime


SENSOR_PATTERN = re.compile(
    r"^I:(?P<imei>\d+),P:(?P<ip>[\d.]+),(?P<temp>\d+),(?P<ppm>\d+)$"
)


def parse_line(raw: str) -> dict | None:
    line = raw.strip()
    if not line:
        return None

    match = SENSOR_PATTERN.match(line)
    if match:
        temp_raw = int(match.group("temp"))
        return {
            "imei": match.group("imei"),
            "ip": match.group("ip"),
            "temperature": temp_raw / 10.0,
            "gas_ppm": int(match.group("ppm")),
            "raw_message": line,
            "message_type": "sensor",
            "timestamp": datetime.utcnow(),
        }

    upper = line.upper()
    if "COMANDO OK" in upper or "COMANDO EJECUTADO" in upper:
        return {
            "imei": None,
            "ip": None,
            "temperature": None,
            "gas_ppm": None,
            "raw_message": "COMANDO EJECUTADO" if "EJECUTADO" in upper else line,
            "message_type": "command_ack",
            "timestamp": datetime.utcnow(),
        }

    return {
        "imei": None,
        "ip": None,
        "temperature": None,
        "gas_ppm": None,
        "raw_message": line,
        "message_type": "raw",
        "timestamp": datetime.utcnow(),
    }

from app.display_service import get_display_rules
from app.display_transform import DisplayRules, apply_client_sensor_values, transform_gas_ppm, transform_temperature
from app.models import Reading
from app.schemas import ChartPoint, ReadingOut
from app.timezone_util import from_utc_naive
from sqlalchemy.orm import Session


def build_reading_out(reading: Reading, role: str, rules: DisplayRules) -> ReadingOut:
    temp_raw = reading.temperature
    gas_raw = reading.gas_ppm
    temp_display, gas_display = apply_client_sensor_values(temp_raw, gas_raw, rules)

    if role == "admin":
        return ReadingOut(
            id=reading.id,
            imei=reading.imei,
            ip=reading.ip,
            temperature=temp_raw,
            gas_ppm=gas_raw,
            temperature_raw=temp_raw,
            gas_ppm_raw=gas_raw,
            temperature_display=temp_display,
            gas_display=gas_display,
            raw_message=reading.raw_message,
            message_type=reading.message_type,
            received_at=reading.received_at,
            is_raw=True,
        )

    return ReadingOut(
        id=reading.id,
        imei=reading.imei,
        ip=reading.ip,
        temperature=temp_display,
        gas_ppm=None,
        temperature_raw=None,
        gas_ppm_raw=None,
        temperature_display=temp_display,
        gas_display=gas_display,
        raw_message=reading.raw_message,
        message_type=reading.message_type,
        received_at=reading.received_at,
        is_raw=False,
    )


def build_chart_point(reading: Reading, role: str, rules: DisplayRules) -> ChartPoint:
    if role == "admin":
        return ChartPoint(
            timestamp=from_utc_naive(reading.received_at),
            temperature=reading.temperature,
            gas_ppm=reading.gas_ppm,
            gas_display=transform_gas_ppm(reading.gas_ppm, rules),
            temperature_display=reading.temperature,
        )
    temp_d, gas_d = apply_client_sensor_values(reading.temperature, reading.gas_ppm, rules)
    return ChartPoint(
        timestamp=from_utc_naive(reading.received_at),
        temperature=temp_d,
        gas_ppm=None,
        gas_display=gas_d,
        temperature_display=temp_d,
    )


def get_rules(db: Session) -> DisplayRules:
    return get_display_rules(db)

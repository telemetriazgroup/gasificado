from datetime import datetime

from pydantic import BaseModel, field_serializer

from app.timezone_util import from_utc_naive


class TelemetryIn(BaseModel):
    imei: str | None = None
    ip: str | None = None
    temperature: float | None = None
    gas_ppm: int | None = None
    raw_message: str
    message_type: str = "sensor"
    client_ip: str | None = None
    timestamp: datetime | None = None


class TerminalIn(BaseModel):
    imei: str | None = None
    direction: str
    message: str
    timestamp: datetime | None = None


class ConnectionStatusIn(BaseModel):
    imei: str
    ip: str
    connected: bool


class ReadingOut(BaseModel):
    id: int
    imei: str
    ip: str | None
    temperature: float | None
    gas_ppm: int | None
    raw_message: str
    message_type: str
    received_at: datetime

    @field_serializer("received_at")
    def serialize_received(self, value: datetime):
        local = from_utc_naive(value)
        return local.isoformat() if local else value.isoformat()

    class Config:
        from_attributes = True


class DeviceOut(BaseModel):
    imei: str
    last_ip: str | None
    last_seen_at: datetime | None
    is_connected: bool

    @field_serializer("last_seen_at")
    def serialize_seen(self, value: datetime | None):
        if value is None:
            return None
        local = from_utc_naive(value)
        return local.isoformat() if local else value.isoformat()

    class Config:
        from_attributes = True


class CommandRequest(BaseModel):
    imei: str
    command: str
    append_newline: bool = True


class CommandResponse(BaseModel):
    success: bool
    message: str
    command: str


class ChartPoint(BaseModel):
    timestamp: datetime
    temperature: float | None
    gas_ppm: int | None

    @field_serializer("timestamp")
    def serialize_ts(self, value: datetime):
        local = from_utc_naive(value) if value.tzinfo is None else value
        return local.isoformat()


class ChartData(BaseModel):
    imei: str
    points: list[ChartPoint]


class LatestData(BaseModel):
    device: DeviceOut | None
    latest_reading: ReadingOut | None
    last_command: dict | None = None
    timezone: str = "America/Bogota"


class SetPointRequest(BaseModel):
    imei: str
    temperature: float
    gas_ppm: int
    apply_to_device: bool = True


class SetPointOut(BaseModel):
    imei: str
    temperature: float
    gas_ppm: int
    updated_by: str
    updated_at: datetime
    applied: bool

    @field_serializer("updated_at")
    def serialize_updated(self, value: datetime):
        local = from_utc_naive(value)
        return local.isoformat() if local else value.isoformat()

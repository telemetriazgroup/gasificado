from datetime import datetime

from pydantic import BaseModel, Field


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

    class Config:
        from_attributes = True


class DeviceOut(BaseModel):
    imei: str
    last_ip: str | None
    last_seen_at: datetime | None
    is_connected: bool

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


class ChartData(BaseModel):
    imei: str
    points: list[ChartPoint]


class LatestData(BaseModel):
    device: DeviceOut | None
    latest_reading: ReadingOut | None
    last_command: dict | None = None

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    imei: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    last_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_connected: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Reading(Base):
    __tablename__ = "readings"

    id: Mapped[int] = mapped_column(primary_key=True)
    imei: Mapped[str] = mapped_column(String(20), index=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    gas_ppm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_message: Mapped[str] = mapped_column(Text)
    message_type: Mapped[str] = mapped_column(String(30), default="sensor")
    received_at: Mapped[datetime] = mapped_column(DateTime, index=True, default=datetime.utcnow)

    __table_args__ = (Index("ix_readings_imei_received", "imei", "received_at"),)


class CommandLog(Base):
    __tablename__ = "command_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    imei: Mapped[str] = mapped_column(String(20), index=True)
    command: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default="sent")
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ack_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class TerminalLog(Base):
    __tablename__ = "terminal_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    imei: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    direction: Mapped[str] = mapped_column(String(10))
    message: Mapped[str] = mapped_column(Text)
    logged_at: Mapped[datetime] = mapped_column(DateTime, index=True, default=datetime.utcnow)


class SetPoint(Base):
    __tablename__ = "setpoints"

    id: Mapped[int] = mapped_column(primary_key=True)
    imei: Mapped[str] = mapped_column(String(20), index=True)
    temperature: Mapped[float] = mapped_column(Float)
    gas_ppm: Mapped[int] = mapped_column(Integer)
    updated_by: Mapped[str] = mapped_column(String(50))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    applied: Mapped[bool] = mapped_column(default=False)

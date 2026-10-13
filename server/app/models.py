from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, utcnow


class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), default="photo")  # photo | calibration
    original_name: Mapped[str] = mapped_column(String(255))
    original_ext: Mapped[str] = mapped_column(String(10))
    src_width: Mapped[int] = mapped_column(Integer)
    src_height: Mapped[int] = mapped_column(Integer)
    # Recorte en píxeles de la imagen original (ya corregida por EXIF). None = centrado automático
    crop_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    crop_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    crop_w: Mapped[float | None] = mapped_column(Float, nullable=True)
    crop_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    etag: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_shown_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    show_count: Mapped[int] = mapped_column(Integer, default=0)


class QueueItem(Base):
    __tablename__ = "queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    image_id: Mapped[int] = mapped_column(ForeignKey("images.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DeviceState(Base):
    __tablename__ = "device_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    current_image_id: Mapped[int | None] = mapped_column(
        ForeignKey("images.id", ondelete="SET NULL"), nullable=True
    )
    current_since: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    shuffle_bag: Mapped[list] = mapped_column(JSON, default=list)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_sleep_s: Mapped[int | None] = mapped_column(Integer, nullable=True)


class DeviceReport(Base):
    __tablename__ = "device_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    battery_mv: Mapped[int | None] = mapped_column(Integer, nullable=True)  # ya con factor aplicado
    battery_raw_mv: Mapped[int | None] = mapped_column(Integer, nullable=True)  # tal cual lo envía el ESP32
    rssi: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fw: Mapped[str | None] = mapped_column(String(32), nullable=True)
    awake_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wake_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    image_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[int] = mapped_column(Integer)
    sleep_s: Mapped[int] = mapped_column(Integer)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)

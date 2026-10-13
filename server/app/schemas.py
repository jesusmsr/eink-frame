from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, PlainSerializer


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


UtcDatetime = Annotated[datetime, PlainSerializer(_iso, return_type=str)]


class LoginIn(BaseModel):
    password: str


class MeOut(BaseModel):
    authenticated: bool
    version: str


class ImageOut(BaseModel):
    id: int
    kind: str
    original_name: str
    enabled: bool
    created_at: UtcDatetime
    processed_at: UtcDatetime | None
    last_shown_at: UtcDatetime | None
    show_count: int
    etag: str | None
    is_current: bool
    queued: bool


class ImagePatch(BaseModel):
    enabled: bool | None = None


class BatteryOut(BaseModel):
    mv: int | None
    percent: float | None
    low: bool
    critical: bool
    charging: bool
    days_left: float | None


class DeviceStatusOut(BaseModel):
    last_seen: UtcDatetime | None
    next_expected: UtcDatetime | None
    online: bool
    battery: BatteryOut
    rssi: int | None
    fw: str | None
    awake_ms_avg: int | None
    current_image_id: int | None
    current_since: UtcDatetime | None
    next_change: UtcDatetime | None
    reports_24h: int
    queue: list[int]


class ReportOut(BaseModel):
    ts: UtcDatetime
    battery_mv: int | None
    battery_raw_mv: int | None
    percent: float | None
    rssi: int | None
    awake_ms: int | None
    status: int
    sleep_s: int
    image_id: int | None
    wake_reason: str | None
    fw: str | None


class CalibrateBatteryIn(BaseModel):
    measured_mv: int

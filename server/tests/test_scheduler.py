from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from app import battery, scheduler
from app.db import SessionLocal, get_engine
from app.models import Base, Image
from app.settings_store import FrameSettings

from .conftest import upload

TZ = ZoneInfo("Europe/Madrid")


def utc(local: str) -> datetime:
    """'2026-10-14 12:00' en hora de Madrid → UTC naive"""
    dt = datetime.fromisoformat(local).replace(tzinfo=TZ)
    return dt.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def test_migrations_match_models(app):
    with get_engine().connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_rotation_every_interval(admin):
    for s in range(3):
        upload(admin, seed=s)
    st = FrameSettings(interval_minutes=30, check_minutes=30, quiet_enabled=False)
    with SessionLocal() as db:
        t0 = utc("2026-10-14 12:00")
        d1 = scheduler.decide(db, st, TZ, now=t0)
        assert d1.changed and d1.sleep_s == 30 * 60
        # se despierta 60 s antes (deriva del RTC) → cuenta como a tiempo
        d2 = scheduler.decide(db, st, TZ, now=t0 + timedelta(minutes=29))
        assert d2.changed and d2.image.id != d1.image.id
        # a mitad de intervalo no cambia y duerme lo que falta
        d3 = scheduler.decide(db, st, TZ, now=t0 + timedelta(minutes=29 + 10))
        assert not d3.changed and d3.image.id == d2.image.id
        assert d3.sleep_s == 20 * 60


def test_shuffle_shows_all_before_repeating(admin):
    ids = {upload(admin, seed=s)["id"] for s in range(5)}
    st = FrameSettings(interval_minutes=30, quiet_enabled=False, order="shuffle")
    seen = []
    with SessionLocal() as db:
        t = utc("2026-10-14 10:00")
        for _ in range(5):
            seen.append(scheduler.decide(db, st, TZ, now=t).image.id)
            t += timedelta(minutes=30)
    assert set(seen) == ids


def test_sequential(admin):
    ids = [upload(admin, seed=s)["id"] for s in range(3)]
    st = FrameSettings(interval_minutes=30, quiet_enabled=False, order="sequential")
    with SessionLocal() as db:
        t = utc("2026-10-14 10:00")
        got = []
        for _ in range(4):
            got.append(scheduler.decide(db, st, TZ, now=t).image.id)
            t += timedelta(minutes=30)
    assert got == ids + ids[:1]


def test_quiet_hours(admin):
    upload(admin, seed=1)
    upload(admin, seed=2)
    st = FrameSettings(interval_minutes=30, quiet_enabled=True, quiet_start="00:00", quiet_end="07:00")
    with SessionLocal() as db:
        d = scheduler.decide(db, st, TZ, now=utc("2026-10-14 23:50"))
        # la siguiente despertada caería en horas de silencio → dormir hasta las 7:00
        assert d.sleep_s == int(timedelta(hours=7, minutes=10).total_seconds())
        current = d.image.id
        d = scheduler.decide(db, st, TZ, now=utc("2026-10-15 03:00"))
        assert d.quiet and d.image.id == current and not d.changed
        assert d.sleep_s == 4 * 3600
        d = scheduler.decide(db, st, TZ, now=utc("2026-10-15 07:00"))
        assert not d.quiet and d.changed


def test_quiet_window_across_midnight():
    from datetime import time

    assert scheduler.in_window(time(23, 30), time(23, 0), time(7, 0))
    assert scheduler.in_window(time(3, 0), time(23, 0), time(7, 0))
    assert not scheduler.in_window(time(12, 0), time(23, 0), time(7, 0))
    assert not scheduler.in_window(time(12, 0), time(7, 0), time(7, 0))


def test_low_battery_sleeps_longer(admin):
    upload(admin)
    st = FrameSettings(interval_minutes=30, quiet_enabled=False, battery_low_mv=3500, low_battery_interval_factor=2)
    with SessionLocal() as db:
        d = scheduler.decide(db, st, TZ, battery_mv=3400, now=utc("2026-10-14 12:00"))
        assert d.sleep_s == 60 * 60


def test_disabled_images_never_shown(admin):
    a = upload(admin, seed=1)
    upload(admin, seed=2)
    with SessionLocal() as db:
        db.get(Image, a["id"]).enabled = False
        db.commit()
        st = FrameSettings(quiet_enabled=False)
        t = utc("2026-10-14 10:00")
        for _ in range(4):
            assert scheduler.decide(db, st, TZ, now=t).image.id != a["id"]
            t += timedelta(minutes=30)


def test_battery_percent():
    assert battery.percent(4250) == 100
    assert battery.percent(3000) == 0
    assert battery.percent(3840) == 50
    assert 40 < battery.percent(3810) < 45


def test_days_left():
    t0 = datetime(2026, 10, 1)
    # 4.10 V → 3.80 V en 5 días
    pts = [(t0 + timedelta(hours=12 * i), int(4100 - 30 * i)) for i in range(11)]
    d = battery.estimate_days_left(pts)
    assert d is not None and 3 < d < 15


def test_button_forces_next_even_at_night(admin):
    upload(admin, seed=1)
    upload(admin, seed=2)
    st = FrameSettings(interval_minutes=30, quiet_enabled=True)
    with SessionLocal() as db:
        d1 = scheduler.decide(db, st, TZ, now=utc("2026-10-14 12:00"))
        d2 = scheduler.decide(db, st, TZ, now=utc("2026-10-14 12:05"), force_next=True)
        assert d2.changed and d2.image.id != d1.image.id
        d3 = scheduler.decide(db, st, TZ, now=utc("2026-10-15 02:00"), force_next=True)
        assert d3.changed and d3.image.id != d2.image.id

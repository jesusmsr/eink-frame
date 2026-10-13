"""Decide qué imagen debe mostrar el marco y cuánto tiempo debe dormir."""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import DeviceState, Image, QueueItem
from .settings_store import FrameSettings

MIN_SLEEP_S = 60
MAX_SLEEP_S = 24 * 3600


@dataclass
class Decision:
    image: Image | None
    sleep_s: int
    quiet: bool
    changed: bool  # True si en esta llamada se ha elegido una imagen nueva


def get_state(db: Session) -> DeviceState:
    state = db.get(DeviceState, 1)
    if state is None:
        state = DeviceState(id=1, shuffle_bag=[])
        db.add(state)
        db.flush()
    return state


def _parse(t: str) -> time:
    h, m = t.split(":")
    return time(int(h), int(m))


def in_window(now: time, start: time, end: time) -> bool:
    if start == end:
        return False
    if start < end:
        return start <= now < end
    return now >= start or now < end  # cruza medianoche


def _next_local(now_local: datetime, at: time) -> datetime:
    candidate = now_local.replace(hour=at.hour, minute=at.minute, second=0, microsecond=0)
    if candidate <= now_local:
        candidate += timedelta(days=1)
    return candidate


def _playable(db: Session) -> list[Image]:
    return list(
        db.scalars(
            select(Image)
            .where(Image.enabled.is_(True), Image.etag.is_not(None))
            .order_by(Image.created_at, Image.id)
        )
    )


def choose_next(db: Session, state: DeviceState, settings: FrameSettings, current: Image | None) -> Image | None:
    images = _playable(db)
    if not images:
        return None
    by_id = {i.id: i for i in images}
    current_id = current.id if current else None

    if settings.order == "sequential":
        ids = [i.id for i in images]
        if current_id in ids:
            return by_id[ids[(ids.index(current_id) + 1) % len(ids)]]
        # la actual se borró o desactivó: la siguiente por fecha
        if current is not None:
            later = [i for i in images if (i.created_at, i.id) > (current.created_at, current.id)]
            if later:
                return later[0]
        return images[0]

    candidates = [i for i in images if i.id != current_id] or images
    if settings.order == "random":
        return random.choice(candidates)

    # shuffle: "bolsa" sin repetición hasta que se hayan mostrado todas
    bag = [i for i in (state.shuffle_bag or []) if i in by_id and i != current_id]
    if not bag:
        bag = [i.id for i in candidates]
        random.shuffle(bag)
    pick = bag.pop(0)
    state.shuffle_bag = bag
    return by_id[pick]


def decide(
    db: Session,
    settings: FrameSettings,
    tz: ZoneInfo,
    battery_mv: int | None = None,
    now: datetime | None = None,
    force_next: bool = False,
) -> Decision:
    """force_next=True (botón físico del marco): pasa a la siguiente foto aunque no toque."""
    now_utc = now or datetime.now(timezone.utc).replace(tzinfo=None)
    now_local = now_utc.replace(tzinfo=timezone.utc).astimezone(tz)
    state = get_state(db)

    q_start, q_end = _parse(settings.quiet_start), _parse(settings.quiet_end)
    quiet = settings.quiet_enabled and in_window(now_local.time(), q_start, q_end)

    current = db.get(Image, state.current_image_id) if state.current_image_id else None
    if current is not None and (not current.enabled or current.etag is None):
        current = None

    interval = timedelta(minutes=settings.interval_minutes)
    # El reloj RTC del ESP32 deriva bastante: si llega un poco antes, se cuenta como "a tiempo"
    tolerance = max(timedelta(seconds=90), interval * 0.05)

    changed = False
    pick: Image | None = None
    if not quiet or force_next:
        while True:
            item = db.scalars(select(QueueItem).order_by(QueueItem.id).limit(1)).first()
            if item is None:
                break
            db.delete(item)
            img = db.get(Image, item.image_id)
            if img is not None and img.enabled and img.etag:
                pick = img
                break
        if pick is None and (
            force_next
            or current is None
            or state.current_since is None
            or now_utc >= state.current_since + interval - tolerance
        ):
            pick = choose_next(db, state, settings, current)
    elif current is None:
        # De noche no se cambia, salvo que no haya nada asignado todavía
        pick = choose_next(db, state, settings, None)

    if pick is not None:
        changed = current is None or pick.id != current.id
        state.current_image_id = pick.id
        state.current_since = now_utc
        current = pick

    # ---- cuánto dormir ----
    if quiet:
        wake_local = _next_local(now_local, q_end)
        sleep_s = (wake_local - now_local).total_seconds()
    else:
        if current is not None and state.current_since is not None:
            until_change = (state.current_since + interval - now_utc).total_seconds()
        else:
            until_change = interval.total_seconds()
        sleep_s = min(max(until_change, 0), settings.check_minutes * 60)
        if battery_mv is not None and battery_mv < settings.battery_low_mv:
            sleep_s *= settings.low_battery_interval_factor
        if settings.quiet_enabled and q_start != q_end:
            wake_local = now_local + timedelta(seconds=sleep_s)
            if in_window(wake_local.time(), q_start, q_end):
                sleep_s = (_next_local(now_local, q_end) - now_local).total_seconds()

    sleep_s = int(min(max(sleep_s, MIN_SLEEP_S), MAX_SLEEP_S))
    state.last_seen = now_utc
    state.last_sleep_s = sleep_s
    return Decision(image=current, sleep_s=sleep_s, quiet=quiet, changed=changed)

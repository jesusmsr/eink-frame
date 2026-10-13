from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import battery, scheduler
from ..db import get_db, utcnow
from ..models import DeviceReport, QueueItem
from ..schemas import BatteryOut, CalibrateBatteryIn, DeviceStatusOut, ReportOut
from ..security import client_ip, require_admin, require_device
from ..settings_store import get_settings, save_settings

router = APIRouter(prefix="/api/device", tags=["device"])

# Margen para considerar "online" al marco (refresco de ~40 s + deriva del RTC)
ONLINE_GRACE = timedelta(minutes=10)


def _clean_etag(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip()
    if v.startswith("W/"):
        v = v[2:]
    return v.strip('"') or None


@router.get(
    "/frame",
    dependencies=[Depends(require_device)],
    response_class=Response,
    responses={
        200: {"content": {"application/octet-stream": {}}, "description": "Imagen nativa 4bpp 800x480"},
        204: {"description": "No hay imágenes"},
        304: {"description": "Sin cambios"},
    },
)
def frame(
    request: Request,
    # Sin validación estricta: un valor raro no debe dejar al marco sin imagen (se recorta)
    bat: int | None = Query(None, description="mV medidos por el ESP32 (sin corregir)"),
    rssi: int | None = Query(None),
    fw: str | None = Query(None),
    awake: int | None = Query(None, description="ms despierto en el ciclo anterior"),
    wake: str | None = Query(None),
    if_none_match: str | None = Header(None),
    db: Session = Depends(get_db),
) -> Response:
    cfg = request.app.state.config
    bat = bat if bat is not None and 1000 <= bat <= 6000 else None
    rssi = max(-127, min(rssi, 0)) if rssi is not None else None
    awake = max(0, min(awake, 24 * 3600 * 1000)) if awake is not None else None
    fw = fw[:32] if fw else None
    wake = wake[:32] if wake else None
    settings = get_settings(db)
    battery_mv = round(bat * settings.battery_factor) if bat else None

    decision = scheduler.decide(db, settings, cfg.timezone, battery_mv, force_next=(wake == "button"))
    img = decision.image
    device_etag = _clean_etag(if_none_match)

    headers = {
        "X-Sleep-Seconds": str(decision.sleep_s),
        "X-Rotation": str(settings.rotation),
        "X-Battery-Factor": str(round(settings.battery_factor * 1000)),
        "X-Battery-Low-Mv": str(settings.battery_low_mv),
        "X-Battery-Critical-Mv": str(settings.battery_critical_mv),
        "Cache-Control": "no-store",
    }

    body = b""
    if img is None:
        code = status.HTTP_204_NO_CONTENT
    else:
        headers["X-Image-Id"] = str(img.id)
        headers["ETag"] = f'"{img.etag}"'
        if device_etag == img.etag:
            code = status.HTTP_304_NOT_MODIFIED
        else:
            path = request.app.state.storage.native(img.id)
            try:
                body = path.read_bytes()
            except FileNotFoundError:
                raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Imagen sin procesar") from None
            code = status.HTTP_200_OK
            img.last_shown_at = utcnow()
            img.show_count = (img.show_count or 0) + 1

    report = DeviceReport(
        battery_mv=battery_mv,
        battery_raw_mv=bat,
        rssi=rssi,
        fw=fw,
        awake_ms=awake,
        wake_reason=wake,
        image_id=img.id if img else None,
        status=code,
        sleep_s=decision.sleep_s,
        ip=client_ip(request),
    )
    db.add(report)
    db.flush()
    if report.id % 50 == 0:
        cutoff = utcnow() - timedelta(days=cfg.report_retention_days)
        db.execute(delete(DeviceReport).where(DeviceReport.ts < cutoff))
    db.commit()

    if code == status.HTTP_200_OK:
        return Response(body, status_code=code, media_type="application/octet-stream", headers=headers)
    return Response(status_code=code, headers=headers)


# ---------- panel ----------

def _battery(db: Session, settings) -> BatteryOut:
    since = utcnow() - timedelta(hours=72)
    rows = list(
        db.execute(
            select(DeviceReport.ts, DeviceReport.battery_mv)
            .where(DeviceReport.ts >= since, DeviceReport.battery_mv.is_not(None))
            .order_by(DeviceReport.ts)
        )
    )
    mv = rows[-1][1] if rows else None
    charging = len(rows) >= 3 and rows[-1][1] - rows[-3][1] > 40
    return BatteryOut(
        mv=mv,
        percent=battery.percent(mv),
        low=mv is not None and mv < settings.battery_low_mv,
        critical=mv is not None and mv < settings.battery_critical_mv,
        charging=charging,
        days_left=None if charging else battery.estimate_days_left([(t, v) for t, v in rows]),
    )


@router.get("", response_model=DeviceStatusOut, dependencies=[Depends(require_admin)])
def device_status(db: Session = Depends(get_db)) -> DeviceStatusOut:
    settings = get_settings(db)
    state = scheduler.get_state(db)
    db.commit()
    now = utcnow()
    last = db.scalars(select(DeviceReport).order_by(DeviceReport.id.desc()).limit(1)).first()
    next_expected = (
        state.last_seen + timedelta(seconds=state.last_sleep_s) if state.last_seen and state.last_sleep_s else None
    )
    day = list(
        db.scalars(select(DeviceReport.awake_ms).where(DeviceReport.ts >= now - timedelta(hours=24)))
    )
    awake = [a for a in day if a is not None]
    return DeviceStatusOut(
        last_seen=state.last_seen,
        next_expected=next_expected,
        online=bool(next_expected and now <= next_expected + ONLINE_GRACE),
        battery=_battery(db, settings),
        rssi=last.rssi if last else None,
        fw=last.fw if last else None,
        awake_ms_avg=round(sum(awake) / len(awake)) if awake else None,
        current_image_id=state.current_image_id,
        current_since=state.current_since,
        next_change=(
            state.current_since + timedelta(minutes=settings.interval_minutes) if state.current_since else None
        ),
        reports_24h=len(day),
        queue=list(db.scalars(select(QueueItem.image_id).order_by(QueueItem.id))),
    )


@router.get("/reports", response_model=list[ReportOut], dependencies=[Depends(require_admin)])
def reports(hours: int = Query(168, ge=1, le=24 * 180), db: Session = Depends(get_db)) -> list[ReportOut]:
    since = utcnow() - timedelta(hours=hours)
    rows = db.scalars(select(DeviceReport).where(DeviceReport.ts >= since).order_by(DeviceReport.ts))
    return [
        ReportOut(
            ts=r.ts,
            battery_mv=r.battery_mv,
            battery_raw_mv=r.battery_raw_mv,
            percent=battery.percent(r.battery_mv),
            rssi=r.rssi,
            awake_ms=r.awake_ms,
            status=r.status,
            sleep_s=r.sleep_s,
            image_id=r.image_id,
            wake_reason=r.wake_reason,
            fw=r.fw,
        )
        for r in rows
    ]


@router.post("/calibrate-battery", response_model=BatteryOut, dependencies=[Depends(require_admin)])
def calibrate_battery(body: CalibrateBatteryIn, db: Session = Depends(get_db)) -> BatteryOut:
    """Ajusta el factor del ADC con una lectura del multímetro tomada justo después
    del último informe del marco."""
    last = db.scalars(
        select(DeviceReport)
        .where(DeviceReport.battery_raw_mv.is_not(None))
        .order_by(DeviceReport.id.desc())
        .limit(1)
    ).first()
    if last is None or not last.battery_raw_mv:
        raise HTTPException(status.HTTP_409_CONFLICT, "Todavía no hay lecturas del marco")
    if not 2500 <= body.measured_mv <= 4500:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Lectura fuera de rango (2500–4500 mV)")
    settings = get_settings(db)
    factor = body.measured_mv / last.battery_raw_mv
    if not 0.5 <= factor <= 1.5:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Factor resultante absurdo ({factor:.3f})")
    settings.battery_factor = round(factor, 4)
    save_settings(db, settings)
    last.battery_mv = body.measured_mv
    db.commit()
    return _battery(db, settings)

"""Estimación del porcentaje de una LiPo 1S a partir de la tensión en reposo."""
from __future__ import annotations

from datetime import datetime

# (mV, %) curva típica de descarga de LiPo en reposo / carga muy baja
_CURVE = [
    (4200, 100), (4150, 95), (4110, 90), (4080, 85), (4020, 80), (3980, 75),
    (3950, 70), (3910, 65), (3870, 60), (3850, 55), (3840, 50), (3820, 45),
    (3800, 40), (3790, 35), (3770, 30), (3750, 25), (3730, 20), (3710, 15),
    (3690, 10), (3610, 5), (3270, 0),
]


def percent(mv: int | None) -> float | None:
    if mv is None:
        return None
    if mv >= _CURVE[0][0]:
        return 100.0
    if mv <= _CURVE[-1][0]:
        return 0.0
    for (v_hi, p_hi), (v_lo, p_lo) in zip(_CURVE, _CURVE[1:]):
        if v_lo <= mv <= v_hi:
            return round(p_lo + (mv - v_lo) * (p_hi - p_lo) / (v_hi - v_lo), 1)
    return None  # pragma: no cover


def estimate_days_left(points: list[tuple[datetime, int]]) -> float | None:
    """Regresión lineal del % frente al tiempo con los informes recientes.
    Devuelve None si no hay datos suficientes o la batería no está bajando."""
    pts = [(t, percent(mv)) for t, mv in points if mv is not None]
    pts = [(t, p) for t, p in pts if p is not None]
    if len(pts) < 6:
        return None
    t0 = pts[0][0]
    xs = [(t - t0).total_seconds() / 86400 for t, _ in pts]
    ys = [p for _, p in pts]
    if xs[-1] - xs[0] < 0.25:  # menos de 6 h de datos
        return None
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx  # %/día
    if slope >= -0.05:
        return None
    return round(ys[-1] / -slope, 1)

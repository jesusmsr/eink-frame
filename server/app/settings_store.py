"""Ajustes del marco, guardados como un único JSON en la tabla app_settings."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from .models import AppSettings

HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

# Orden = código nativo del controlador ACeP (0 negro, 1 blanco, 2 verde, 3 azul, 4 rojo, 5 amarillo, 6 naranja)
PALETTE_NAMES = ["black", "white", "green", "blue", "red", "yellow", "orange"]

# Paleta "realista" de partida: los pigmentos ACeP son bastante más apagados que el RGB puro.
# Se ajusta en la fase de calibración (Ajustes → Paleta) fotografiando la carta de colores.
DEFAULT_PALETTE = ["#1c1a1f", "#e6e6dc", "#2e6e42", "#2f3a8c", "#b02a2a", "#e8d23a", "#d46a2c"]
IDEAL_PALETTE = ["#000000", "#ffffff", "#00ff00", "#0000ff", "#ff0000", "#ffff00", "#ff8000"]

# Campos que, si cambian, obligan a regenerar todas las imágenes
IMAGE_FIELDS = {"rotation", "saturation", "contrast", "brightness", "dither", "palette"}


class FrameSettings(BaseModel):
    # Rotación
    interval_minutes: int = Field(30, ge=5, le=24 * 60, description="Cuánto tiempo se muestra cada foto")
    check_minutes: int = Field(
        30, ge=5, le=24 * 60,
        description="Cada cuánto despierta como máximo el marco para ver si hay algo en cola",
    )
    order: Literal["shuffle", "sequential", "random"] = "shuffle"
    quiet_enabled: bool = True
    quiet_start: str = "00:00"
    quiet_end: str = "07:00"

    # Imagen
    rotation: int = Field(3, ge=0, le=3, description="Igual que setRotation() de GxEPD2. 3 = vertical")
    saturation: float = Field(1.25, ge=0.0, le=3.0)
    contrast: float = Field(1.05, ge=0.0, le=3.0)
    brightness: float = Field(1.0, ge=0.2, le=2.0)
    dither: Literal["floyd_steinberg", "none"] = "floyd_steinberg"
    palette: list[str] = Field(default=list(DEFAULT_PALETTE))

    # Batería
    battery_factor: float = Field(1.0, ge=0.5, le=1.5, description="Corrección de la lectura del ADC")
    battery_low_mv: int = Field(3500, ge=3000, le=4000)
    battery_critical_mv: int = Field(3300, ge=3000, le=3800)
    low_battery_interval_factor: float = Field(2.0, ge=1.0, le=10.0)

    @field_validator("palette")
    @classmethod
    def _palette(cls, v: list[str]) -> list[str]:
        if len(v) != 7 or not all(HEX_RE.match(c) for c in v):
            raise ValueError("La paleta debe tener 7 colores en formato #rrggbb")
        return [c.lower() for c in v]

    @field_validator("quiet_start", "quiet_end")
    @classmethod
    def _time(cls, v: str) -> str:
        if not TIME_RE.match(v):
            raise ValueError("Formato HH:MM")
        return v

    @model_validator(mode="after")
    def _coherent(self) -> "FrameSettings":
        if self.check_minutes > self.interval_minutes:
            self.check_minutes = self.interval_minutes
        if self.battery_critical_mv >= self.battery_low_mv:
            raise ValueError("El umbral crítico debe ser menor que el de batería baja")
        return self

    def palette_rgb(self) -> list[tuple[int, int, int]]:
        return [tuple(int(c[i : i + 2], 16) for i in (1, 3, 5)) for c in self.palette]  # type: ignore[misc]


def get_settings(db: Session) -> FrameSettings:
    row = db.get(AppSettings, 1)
    if row is None:
        return FrameSettings()
    # model_validate rellena con valores por defecto los campos nuevos
    return FrameSettings.model_validate({**FrameSettings().model_dump(), **(row.data or {})})


def save_settings(db: Session, settings: FrameSettings) -> None:
    row = db.get(AppSettings, 1)
    if row is None:
        row = AppSettings(id=1, data={})
        db.add(row)
    row.data = settings.model_dump()
    db.commit()


def image_fields_changed(old: FrameSettings, new: FrameSettings) -> bool:
    o, n = old.model_dump(), new.model_dump()
    return any(o[k] != n[k] for k in IMAGE_FIELDS)

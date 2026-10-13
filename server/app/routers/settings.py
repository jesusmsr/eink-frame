from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import reprocess
from ..db import get_db
from ..security import require_admin
from ..settings_store import (
    DEFAULT_PALETTE,
    IDEAL_PALETTE,
    PALETTE_NAMES,
    FrameSettings,
    get_settings,
    image_fields_changed,
    save_settings,
)

router = APIRouter(prefix="/api/settings", tags=["settings"], dependencies=[Depends(require_admin)])


class SettingsMeta(BaseModel):
    palette_names: list[str]
    palette_default: list[str]
    palette_ideal: list[str]
    defaults: FrameSettings


class ReprocessStatus(BaseModel):
    running: bool
    done: int
    total: int
    errors: int


@router.get("", response_model=FrameSettings)
def read_settings(db: Session = Depends(get_db)) -> FrameSettings:
    return get_settings(db)


@router.put("", response_model=FrameSettings)
def update_settings(body: FrameSettings, request: Request, db: Session = Depends(get_db)) -> FrameSettings:
    old = get_settings(db)
    save_settings(db, body)
    if image_fields_changed(old, body):
        reprocess.start(request.app)
    return get_settings(db)


@router.get("/meta", response_model=SettingsMeta)
def meta() -> SettingsMeta:
    return SettingsMeta(
        palette_names=PALETTE_NAMES,
        palette_default=DEFAULT_PALETTE,
        palette_ideal=IDEAL_PALETTE,
        defaults=FrameSettings(),
    )


@router.get("/reprocess", response_model=ReprocessStatus)
def reprocess_status(request: Request) -> ReprocessStatus:
    return ReprocessStatus(**reprocess.status(request.app))

"""Regeneración en segundo plano de todas las imágenes (tras cambiar paleta, orientación…)."""
from __future__ import annotations

import logging
import threading

from fastapi import FastAPI
from sqlalchemy import select

from .db import SessionLocal
from .models import Image
from .settings_store import get_settings
from .storage import reprocess

log = logging.getLogger("eink.reprocess")


class _State:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.running = False
        self.again = False
        self.done = 0
        self.total = 0
        self.errors = 0


def _state(app: FastAPI) -> _State:
    if not hasattr(app.state, "reprocess"):
        app.state.reprocess = _State()
    return app.state.reprocess


def status(app: FastAPI) -> dict:
    s = _state(app)
    return {"running": s.running, "done": s.done, "total": s.total, "errors": s.errors}


def _run(app: FastAPI) -> None:
    s = _state(app)
    storage = app.state.storage
    while True:
        with SessionLocal() as db:
            settings = get_settings(db)
            ids = list(db.scalars(select(Image.id)))
            s.done, s.total, s.errors = 0, len(ids), 0
            for image_id in ids:
                if s.again:
                    break  # han vuelto a cambiar los ajustes: empezar de nuevo
                img = db.get(Image, image_id)
                if img is None:
                    continue
                try:
                    reprocess(db, storage, settings, img)
                except Exception:  # noqa: BLE001
                    s.errors += 1
                    log.exception("Error reprocesando imagen %s", image_id)
                    db.rollback()
                s.done += 1
        with s.lock:
            if s.again:
                s.again = False
                continue
            s.running = False
            return


def start(app: FastAPI, wait: bool = False) -> None:
    s = _state(app)
    with s.lock:
        if s.running:
            s.again = True
            return
        s.running = True
    t = threading.Thread(target=_run, args=(app,), daemon=True, name="reprocess")
    t.start()
    if wait:
        t.join()

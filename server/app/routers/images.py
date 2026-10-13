from __future__ import annotations

import io
import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .. import imaging, reprocess
from ..db import get_db
from ..imaging import Crop, ImageError
from ..models import Image, QueueItem
from ..scheduler import get_state
from ..schemas import ImageOut, ImagePatch
from ..security import require_admin
from ..settings_store import get_settings
from ..storage import Storage, create_image

router = APIRouter(prefix="/api", tags=["images"], dependencies=[Depends(require_admin)])


def _storage(request: Request) -> Storage:
    return request.app.state.storage


def _parse_crop(raw: str | None) -> Crop | None:
    if not raw:
        return None
    try:
        d = json.loads(raw)
        w = float(d.get("w", d.get("width")))
        h = float(d.get("h", d.get("height")))
        crop = Crop(float(d["x"]), float(d["y"]), w, h)
    except (ValueError, KeyError, TypeError) as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Recorte inválido") from e
    if crop.w <= 0 or crop.h <= 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Recorte inválido")
    return crop


async def _read_upload(request: Request, file: UploadFile) -> bytes:
    limit = request.app.state.config.max_upload_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"Máximo {limit // (1024 * 1024)} MB")
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Fichero vacío")
    return data


def to_out(db: Session, images: list[Image]) -> list[ImageOut]:
    state = get_state(db)
    queued = set(db.scalars(select(QueueItem.image_id)))
    return [
        ImageOut(
            id=i.id,
            kind=i.kind,
            original_name=i.original_name,
            enabled=i.enabled,
            created_at=i.created_at,
            processed_at=i.processed_at,
            last_shown_at=i.last_shown_at,
            show_count=i.show_count,
            etag=i.etag,
            is_current=state.current_image_id == i.id,
            queued=i.id in queued,
        )
        for i in images
    ]


def _get(db: Session, image_id: int) -> Image:
    img = db.get(Image, image_id)
    if img is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Imagen no encontrada")
    return img


@router.get("/images", response_model=list[ImageOut])
def list_images(db: Session = Depends(get_db)) -> list[ImageOut]:
    images = list(db.scalars(select(Image).order_by(Image.created_at.desc(), Image.id.desc())))
    return to_out(db, images)


@router.post("/images", response_model=ImageOut, status_code=status.HTTP_201_CREATED)
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    crop: str | None = Form(None),
    show_next: bool = Form(False),
    db: Session = Depends(get_db),
) -> ImageOut:
    data = await _read_upload(request, file)
    c = _parse_crop(crop)
    settings = get_settings(db)
    try:
        img = await run_in_threadpool(
            create_image, db, _storage(request), settings, data, Path(file.filename or "imagen").name, c
        )
    except ImageError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    if show_next:
        db.add(QueueItem(image_id=img.id))
        db.commit()
    return to_out(db, [img])[0]


@router.post("/images/preview", response_class=Response, responses={200: {"content": {"image/png": {}}}})
async def preview_image(
    request: Request,
    file: UploadFile = File(...),
    crop: str | None = Form(None),
    db: Session = Depends(get_db),
) -> Response:
    """Procesa sin guardar y devuelve cómo se verá en el panel."""
    data = await _read_upload(request, file)
    c = _parse_crop(crop)
    settings = get_settings(db)
    def _do() -> bytes:
        rendered = imaging.render(imaging.open_source(data), c, settings)
        buf = io.BytesIO()
        rendered.preview.save(buf, "PNG", optimize=False)
        return buf.getvalue()

    try:
        png = await run_in_threadpool(_do)
    except ImageError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    return Response(png, media_type="image/png", headers={"Cache-Control": "no-store"})


@router.post("/images/calibration", response_model=ImageOut, status_code=status.HTTP_201_CREATED)
def create_calibration(request: Request, db: Session = Depends(get_db)) -> ImageOut:
    """Crea la carta de colores y la pone la primera en la cola."""
    settings = get_settings(db)
    src = imaging.calibration_source(settings)
    buf = io.BytesIO()
    src.save(buf, "PNG")
    img = create_image(db, _storage(request), settings, buf.getvalue(), "Carta de calibración", None, kind="calibration")
    db.add(QueueItem(image_id=img.id))
    db.commit()
    return to_out(db, [img])[0]


@router.patch("/images/{image_id}", response_model=ImageOut)
def patch_image(image_id: int, body: ImagePatch, db: Session = Depends(get_db)) -> ImageOut:
    img = _get(db, image_id)
    if body.enabled is not None:
        img.enabled = body.enabled
    db.commit()
    return to_out(db, [img])[0]


@router.delete("/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_image(image_id: int, request: Request, db: Session = Depends(get_db)) -> Response:
    img = _get(db, image_id)
    db.delete(img)
    db.commit()
    _storage(request).delete(image_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _file(path: Path, media_type: str) -> FileResponse:
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fichero no encontrado")
    # El frontend añade ?v=<etag>, así que se puede cachear sin miedo
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "private, max-age=604800"})


@router.get("/images/{image_id}/preview", response_class=FileResponse)
def get_preview(image_id: int, request: Request) -> FileResponse:
    return _file(_storage(request).preview(image_id), "image/png")


@router.get("/images/{image_id}/thumb", response_class=FileResponse)
def get_thumb(image_id: int, request: Request) -> FileResponse:
    return _file(_storage(request).thumb(image_id), "image/jpeg")


@router.get("/images/{image_id}/original", response_class=FileResponse)
def get_original(image_id: int, request: Request, db: Session = Depends(get_db)) -> FileResponse:
    img = _get(db, image_id)
    return _file(_storage(request).original(img), f"image/{'jpeg' if img.original_ext == 'jpg' else img.original_ext}")


# ---- cola ----

@router.get("/queue", response_model=list[int])
def get_queue(db: Session = Depends(get_db)) -> list[int]:
    return list(db.scalars(select(QueueItem.image_id).order_by(QueueItem.id)))


@router.post("/images/{image_id}/show-next", response_model=list[int])
def show_next(image_id: int, db: Session = Depends(get_db)) -> list[int]:
    img = _get(db, image_id)
    if not img.enabled:
        img.enabled = True
    exists = db.scalars(select(QueueItem).where(QueueItem.image_id == image_id)).first()
    if exists is None:
        db.add(QueueItem(image_id=image_id))
    db.commit()
    return get_queue(db)


@router.delete("/queue/{image_id}", response_model=list[int])
def unqueue(image_id: int, db: Session = Depends(get_db)) -> list[int]:
    for item in db.scalars(select(QueueItem).where(QueueItem.image_id == image_id)):
        db.delete(item)
    db.commit()
    return get_queue(db)


@router.post("/images/reprocess", status_code=status.HTTP_202_ACCEPTED)
def reprocess_all(request: Request) -> dict:
    reprocess.start(request.app)
    return reprocess.status(request.app)

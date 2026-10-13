"""Ficheros de cada imagen en /data/images/<id>/."""
from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image as PILImage
from sqlalchemy.orm import Session

from . import imaging
from .db import utcnow
from .imaging import Crop
from .models import Image
from .settings_store import FrameSettings

ALLOWED_FORMATS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "BMP": "bmp", "GIF": "gif", "TIFF": "tif", "MPO": "jpg"}


class Storage:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def dir(self, image_id: int) -> Path:
        return self.root / str(image_id)

    def original(self, img: Image) -> Path:
        return self.dir(img.id) / f"original.{img.original_ext}"

    def native(self, image_id: int) -> Path:
        return self.dir(image_id) / "native.bin"

    def preview(self, image_id: int) -> Path:
        return self.dir(image_id) / "preview.png"

    def thumb(self, image_id: int) -> Path:
        return self.dir(image_id) / "thumb.jpg"

    def delete(self, image_id: int) -> None:
        shutil.rmtree(self.dir(image_id), ignore_errors=True)

    def write_rendered(self, img: Image, rendered: imaging.Rendered) -> None:
        d = self.dir(img.id)
        d.mkdir(parents=True, exist_ok=True)
        tmp = self.native(img.id).with_suffix(".tmp")
        tmp.write_bytes(rendered.native)
        tmp.replace(self.native(img.id))
        rendered.preview.save(self.preview(img.id), optimize=True)
        imaging.make_thumbnail(rendered.preview).save(self.thumb(img.id), quality=85)
        img.etag = rendered.etag
        img.processed_at = utcnow()


def detect_ext(data: bytes) -> str:
    import io

    try:
        with PILImage.open(io.BytesIO(data)) as im:
            fmt = (im.format or "").upper()
    except Exception as e:  # noqa: BLE001
        raise imaging.ImageError("No se reconoce el formato de imagen") from e
    if fmt not in ALLOWED_FORMATS:
        raise imaging.ImageError(f"Formato no soportado: {fmt or 'desconocido'}")
    return ALLOWED_FORMATS[fmt]


def crop_of(img: Image) -> Crop | None:
    if img.crop_w and img.crop_h:
        return Crop(img.crop_x or 0, img.crop_y or 0, img.crop_w, img.crop_h)
    return None


def create_image(
    db: Session,
    storage: Storage,
    settings: FrameSettings,
    data: bytes,
    name: str,
    crop: Crop | None,
    kind: str = "photo",
) -> Image:
    ext = detect_ext(data)
    src = imaging.open_source(data)
    rendered = imaging.render(src, crop, settings, enhance=(kind == "photo"))
    img = Image(
        kind=kind,
        original_name=(name or "imagen")[:255],
        original_ext=ext,
        src_width=src.width,
        src_height=src.height,
        crop_x=crop.x if crop else None,
        crop_y=crop.y if crop else None,
        crop_w=crop.w if crop else None,
        crop_h=crop.h if crop else None,
    )
    db.add(img)
    db.flush()  # asigna id
    try:
        storage.dir(img.id).mkdir(parents=True, exist_ok=True)
        storage.original(img).write_bytes(data)
        storage.write_rendered(img, rendered)
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(img.id)
        raise
    return img


def reprocess(db: Session, storage: Storage, settings: FrameSettings, img: Image) -> None:
    src = imaging.open_source(storage.original(img))
    rendered = imaging.render(src, crop_of(img), settings, enhance=(img.kind == "photo"))
    storage.write_rendered(img, rendered)
    db.commit()

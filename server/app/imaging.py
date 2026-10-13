"""Pipeline de imagen: original → recorte → orientación → ajustes → dithering a la
paleta ACeP → formato nativo del panel (4 bits/píxel, 800×480 = 192.000 bytes)."""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageOps

from .settings_store import FrameSettings

NATIVE_W, NATIVE_H = 800, 480
NATIVE_BYTES = NATIVE_W * NATIVE_H // 2
THUMB_WIDTH = 240

Image.MAX_IMAGE_PIXELS = 80_000_000  # protección frente a "decompression bombs"

# Rotación GxEPD2 → transformación de la imagen lógica a la orientación nativa del panel.
# (setRotation(3): nativo(x, y) = lógico(479 - y, x)  ⇒ girar 90° antihorario)
_TO_NATIVE = {
    0: None,
    1: Image.Transpose.ROTATE_270,
    2: Image.Transpose.ROTATE_180,
    3: Image.Transpose.ROTATE_90,
}


class ImageError(ValueError):
    pass


@dataclass
class Crop:
    x: float
    y: float
    w: float
    h: float


@dataclass
class Rendered:
    native: bytes
    preview: Image.Image  # RGB en orientación lógica, con los colores de la paleta
    etag: str


def logical_size(rotation: int) -> tuple[int, int]:
    return (NATIVE_W, NATIVE_H) if rotation in (0, 2) else (NATIVE_H, NATIVE_W)


def open_source(data: bytes | Path) -> Image.Image:
    """Abre la imagen, aplica la orientación EXIF y la convierte a RGB."""
    try:
        img = Image.open(io.BytesIO(data) if isinstance(data, bytes) else data)
        img.load()
    except Image.DecompressionBombError as e:
        raise ImageError("La imagen es demasiado grande") from e
    except Exception as e:  # noqa: BLE001
        raise ImageError("No se reconoce el formato de imagen") from e
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        return bg
    return img.convert("RGB")


def crop_to_aspect(img: Image.Image, crop: Crop | None, size: tuple[int, int]) -> Image.Image:
    """Recorta con el rectángulo del frontend (si lo hay) y ajusta al tamaño final.
    ImageOps.fit corrige pequeñas desviaciones de proporción del recorte."""
    if crop is not None:
        x0 = max(0.0, min(crop.x, img.width - 1))
        y0 = max(0.0, min(crop.y, img.height - 1))
        x1 = max(x0 + 1, min(crop.x + crop.w, img.width))
        y1 = max(y0 + 1, min(crop.y + crop.h, img.height))
        img = img.crop((round(x0), round(y0), round(x1), round(y1)))
    return ImageOps.fit(img, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def _palette_image(palette: list[tuple[int, int, int]]) -> Image.Image:
    flat: list[int] = []
    for c in palette:
        flat.extend(c)
    # Se rellena repitiendo el último color: cualquier índice ≥ 7 equivale al 6
    flat.extend(list(palette[-1]) * (256 - len(palette)))
    pal = Image.new("P", (1, 1))
    pal.putpalette(flat)
    return pal


def quantize(img: Image.Image, settings: FrameSettings, enhance: bool = True) -> np.ndarray:
    """Devuelve una matriz (alto, ancho) de índices 0..6 en orientación lógica."""
    if enhance:
        if settings.brightness != 1.0:
            img = ImageEnhance.Brightness(img).enhance(settings.brightness)
        if settings.contrast != 1.0:
            img = ImageEnhance.Contrast(img).enhance(settings.contrast)
        if settings.saturation != 1.0:
            img = ImageEnhance.Color(img).enhance(settings.saturation)
    dither = Image.Dither.FLOYDSTEINBERG if settings.dither == "floyd_steinberg" else Image.Dither.NONE
    q = img.quantize(palette=_palette_image(settings.palette_rgb()), dither=dither)
    return np.minimum(np.asarray(q, dtype=np.uint8), 6)


def indices_to_preview(idx: np.ndarray, settings: FrameSettings) -> Image.Image:
    lut = np.array(settings.palette_rgb(), dtype=np.uint8)
    return Image.fromarray(lut[idx], "RGB")


def pack_native(idx: np.ndarray, rotation: int) -> bytes:
    """Gira a la orientación nativa y empaqueta 2 píxeles por byte (nibble alto = píxel izquierdo)."""
    t = _TO_NATIVE[rotation]
    native = Image.fromarray(idx, "L")
    if t is not None:
        native = native.transpose(t)
    arr = np.asarray(native, dtype=np.uint8)
    if arr.shape != (NATIVE_H, NATIVE_W):
        raise ImageError(f"Tamaño nativo inesperado {arr.shape}")
    packed = (arr[:, 0::2] << 4) | arr[:, 1::2]
    data = packed.tobytes()
    assert len(data) == NATIVE_BYTES
    return data


def render(src: Image.Image, crop: Crop | None, settings: FrameSettings, enhance: bool = True) -> Rendered:
    fitted = crop_to_aspect(src, crop, logical_size(settings.rotation))
    idx = quantize(fitted, settings, enhance=enhance)
    native = pack_native(idx, settings.rotation)
    return Rendered(
        native=native,
        preview=indices_to_preview(idx, settings),
        etag=hashlib.sha256(native).hexdigest()[:32],
    )


def make_thumbnail(preview: Image.Image) -> Image.Image:
    h = round(preview.height * THUMB_WIDTH / preview.width)
    return preview.resize((THUMB_WIDTH, h), Image.Resampling.LANCZOS)


def calibration_source(settings: FrameSettings) -> Image.Image:
    """Carta de calibración: 7 franjas con los colores puros del panel + degradados.
    Sirve para fotografiar el panel y ajustar la paleta."""
    w, h = logical_size(settings.rotation)
    img = Image.new("RGB", (w, h), settings.palette_rgb()[1])
    draw = ImageDraw.Draw(img)
    pal = settings.palette_rgb()
    band_h = int(h * 0.62) // 7
    for i, color in enumerate(pal):
        draw.rectangle([0, i * band_h, w, (i + 1) * band_h - 1], fill=color)
    y0 = band_h * 7
    # Degradado de grises
    grad_h = (h - y0) // 2
    gx = np.linspace(0, 255, w, dtype=np.float32)
    gray = np.repeat(gx[None, :], grad_h, axis=0).astype(np.uint8)
    img.paste(Image.fromarray(np.stack([gray] * 3, axis=-1), "RGB"), (0, y0))
    # Arcoíris (tono)
    hue = Image.fromarray(
        np.stack(
            [
                np.repeat(np.linspace(0, 255, w, dtype=np.uint8)[None, :], h - y0 - grad_h, axis=0),
                np.full((h - y0 - grad_h, w), 255, np.uint8),
                np.full((h - y0 - grad_h, w), 255, np.uint8),
            ],
            axis=-1,
        ),
        "HSV",
    ).convert("RGB")
    img.paste(hue, (0, y0 + grad_h))
    return img

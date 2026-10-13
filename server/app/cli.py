"""Utilidades de línea de comandos (se ejecutan dentro del contenedor).

    docker exec -it eink-frame python -m app.cli import /data/import
    docker exec -it eink-frame python -m app.cli reprocess
    docker exec -it eink-frame python -m app.cli token
"""
from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

from sqlalchemy import select

from .config import load_config
from .db import SessionLocal, init_engine
from .imaging import ImageError
from .migrate import upgrade
from .models import Image
from .settings_store import get_settings
from .storage import Storage, create_image, reprocess

IMPORT_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}


def _setup():
    cfg = load_config()
    init_engine(cfg.db_path)
    upgrade(cfg.db_path)
    return cfg, Storage(cfg.images_dir)


def cmd_import(folder: Path) -> int:
    """Importa originales del sistema antiguo. Ignora los *_processed.bmp y los duplicados por nombre."""
    _, storage = _setup()
    files = sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in IMPORT_EXT)
    files = [p for p in files if not p.stem.endswith("_processed")]
    ok = skipped = failed = 0
    with SessionLocal() as db:
        settings = get_settings(db)
        existing = set(db.scalars(select(Image.original_name)))
        for p in files:
            if p.name in existing:
                skipped += 1
                continue
            try:
                create_image(db, storage, settings, p.read_bytes(), p.name, None)
                existing.add(p.name)
                ok += 1
                print(f"  ✓ {p.name}")
            except ImageError as e:
                failed += 1
                print(f"  ✗ {p.name}: {e}")
    print(f"Importadas: {ok} · ya existían: {skipped} · con error: {failed}")
    return 0 if failed == 0 else 1


def cmd_reprocess() -> int:
    _, storage = _setup()
    with SessionLocal() as db:
        settings = get_settings(db)
        imgs = list(db.scalars(select(Image)))
        for i, img in enumerate(imgs, 1):
            reprocess(db, storage, settings, img)
            print(f"  {i}/{len(imgs)} {img.original_name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_imp = sub.add_parser("import", help="Importar imágenes de una carpeta")
    p_imp.add_argument("folder", type=Path, nargs="?", default=Path("/data/import"))
    sub.add_parser("reprocess", help="Regenerar todas las imágenes con los ajustes actuales")
    sub.add_parser("token", help="Generar un token aleatorio (para DEVICE_TOKEN o SECRET_KEY)")
    p_oa = sub.add_parser("openapi", help="Exportar el esquema OpenAPI (para generar los tipos del frontend)")
    p_oa.add_argument("out", type=Path, nargs="?", default=Path("openapi.json"))
    args = ap.parse_args(argv)

    if args.cmd == "import":
        if not args.folder.is_dir():
            print(f"No existe la carpeta {args.folder}", file=sys.stderr)
            return 2
        return cmd_import(args.folder)
    if args.cmd == "reprocess":
        return cmd_reprocess()
    if args.cmd == "openapi":
        import json
        import tempfile

        from .main import create_app

        with tempfile.TemporaryDirectory() as tmp:
            import os

            os.environ["DATA_DIR"] = tmp
            os.environ.setdefault("STATIC_DIR", "")
            schema = create_app().openapi()
        args.out.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n")
        print(f"Escrito {args.out}")
        return 0
    if args.cmd == "token":
        print(secrets.token_urlsafe(32))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

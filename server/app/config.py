"""Configuración leída de variables de entorno."""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Config:
    data_dir: Path
    admin_password: str
    secret_key: str
    device_token: str
    cookie_secure: bool
    timezone: ZoneInfo
    max_upload_bytes: int
    static_dir: Path | None
    version: str
    session_days: int = 30
    report_retention_days: int = 180
    extra: dict = field(default_factory=dict)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "eink.db"

    @property
    def images_dir(self) -> Path:
        return self.data_dir / "images"

    @property
    def import_dir(self) -> Path:
        return self.data_dir / "import"


def _load_or_create_secret(data_dir: Path) -> str:
    """Si no se define SECRET_KEY se genera una y se guarda en /data para que
    las sesiones sobrevivan a reinicios del contenedor."""
    path = data_dir / ".secret_key"
    if path.exists():
        return path.read_text().strip()
    key = secrets.token_urlsafe(48)
    path.write_text(key)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return key


def load_config() -> Config:
    data_dir = Path(os.environ.get("DATA_DIR", "/data")).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    static = os.environ.get("STATIC_DIR", "/app/web")
    static_dir = Path(static) if static and Path(static).is_dir() else None

    return Config(
        data_dir=data_dir,
        admin_password=os.environ.get("ADMIN_PASSWORD", ""),
        secret_key=os.environ.get("SECRET_KEY") or _load_or_create_secret(data_dir),
        device_token=os.environ.get("DEVICE_TOKEN", ""),
        cookie_secure=_bool(os.environ.get("COOKIE_SECURE"), False),
        timezone=ZoneInfo(os.environ.get("TZ", "Europe/Madrid")),
        max_upload_bytes=int(os.environ.get("MAX_UPLOAD_MB", "25")) * 1024 * 1024,
        static_dir=static_dir,
        version=os.environ.get("APP_VERSION", "dev"),
    )

from __future__ import annotations

import io
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import Config
from app.main import create_app

DEVICE_TOKEN = "test-device-token"
PASSWORD = "secreto"


def make_config(tmp_path: Path, static_dir: Path | None = None) -> Config:
    return Config(
        data_dir=tmp_path,
        admin_password=PASSWORD,
        secret_key="x" * 40,
        device_token=DEVICE_TOKEN,
        cookie_secure=False,
        timezone=ZoneInfo("Europe/Madrid"),
        max_upload_bytes=5 * 1024 * 1024,
        static_dir=static_dir,
        version="test",
    )


@pytest.fixture
def app(tmp_path: Path):
    return create_app(make_config(tmp_path))


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture
def admin(client: TestClient) -> TestClient:
    r = client.post("/api/auth/login", json={"password": PASSWORD})
    assert r.status_code == 200, r.text
    return client


def jpeg_bytes(w: int = 1200, h: int = 900, seed: int = 0) -> bytes:
    rng = np.random.default_rng(seed)
    arr = (rng.random((h, w, 3)) * 255).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "JPEG")
    return buf.getvalue()


def upload(client: TestClient, seed: int = 0, crop: str | None = None, name: str = "foto.jpg") -> dict:
    data = {"crop": crop} if crop else {}
    r = client.post("/api/images", files={"file": (name, jpeg_bytes(seed=seed), "image/jpeg")}, data=data)
    assert r.status_code == 201, r.text
    return r.json()


def device_headers(etag: str | None = None) -> dict:
    h = {"Authorization": f"Bearer {DEVICE_TOKEN}"}
    if etag:
        h["If-None-Match"] = etag
    return h

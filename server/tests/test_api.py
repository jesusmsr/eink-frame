from __future__ import annotations

import time

import numpy as np
from fastapi.testclient import TestClient

from app.imaging import NATIVE_BYTES

from .conftest import PASSWORD, device_headers, make_config, upload


def test_health(client: TestClient):
    assert client.get("/api/health").json()["status"] == "ok"


def test_auth_required(client: TestClient):
    for method, url in [("get", "/api/images"), ("get", "/api/settings"), ("get", "/api/device")]:
        assert getattr(client, method)(url).status_code == 401
    r = client.post("/api/images", files={"file": ("a.jpg", b"x", "image/jpeg")})
    assert r.status_code == 401  # la subida ya no es pública


def test_login_and_rate_limit(client: TestClient):
    assert client.get("/api/auth/me").json()["authenticated"] is False
    for _ in range(5):
        assert client.post("/api/auth/login", json={"password": "mal"}).status_code == 401
    assert client.post("/api/auth/login", json={"password": PASSWORD}).status_code == 429


def test_login_logout(client: TestClient):
    assert client.post("/api/auth/login", json={"password": PASSWORD}).status_code == 200
    assert client.get("/api/auth/me").json()["authenticated"] is True
    client.post("/api/auth/logout")
    assert client.get("/api/images").status_code == 401


def test_upload_list_files_delete(admin: TestClient, app):
    img = upload(admin, crop='{"x": 100, "y": 50, "width": 300, "height": 500}')
    assert img["etag"] and img["enabled"]
    listed = admin.get("/api/images").json()
    assert [i["id"] for i in listed] == [img["id"]]
    for kind, ctype in [("preview", "image/png"), ("thumb", "image/jpeg"), ("original", "image/jpeg")]:
        r = admin.get(f"/api/images/{img['id']}/{kind}")
        assert r.status_code == 200 and r.headers["content-type"] == ctype
    assert app.state.storage.native(img["id"]).stat().st_size == NATIVE_BYTES
    assert admin.delete(f"/api/images/{img['id']}").status_code == 204
    assert not app.state.storage.dir(img["id"]).exists()
    assert admin.get("/api/images").json() == []


def test_upload_rejects_garbage(admin: TestClient):
    r = admin.post("/api/images", files={"file": ("x.jpg", b"no soy una imagen", "image/jpeg")})
    assert r.status_code == 422


def test_preview_does_not_store(admin: TestClient):
    from .conftest import jpeg_bytes

    r = admin.post("/api/images/preview", files={"file": ("a.jpg", jpeg_bytes(), "image/jpeg")})
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert admin.get("/api/images").json() == []


def test_device_requires_token(client: TestClient):
    assert client.get("/api/device/frame").status_code == 401
    assert client.get("/api/device/frame", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_device_flow(admin: TestClient):
    r = admin.get("/api/device/frame", headers=device_headers())
    assert r.status_code == 204  # sin imágenes
    assert int(r.headers["x-sleep-seconds"]) >= 60

    img = upload(admin)
    r = admin.get("/api/device/frame?bat=3900&rssi=-60&fw=2.0.0&awake=4000&wake=timer", headers=device_headers())
    assert r.status_code == 200
    assert len(r.content) == NATIVE_BYTES
    assert r.headers["x-image-id"] == str(img["id"])
    assert r.headers["x-rotation"] == "3"
    etag = r.headers["etag"]

    r2 = admin.get("/api/device/frame?bat=3890", headers=device_headers(etag))
    assert r2.status_code == 304 and r2.content == b""

    status = admin.get("/api/device").json()
    assert status["online"] and status["current_image_id"] == img["id"]
    assert status["battery"]["mv"] == 3890
    reports = admin.get("/api/device/reports").json()
    assert [x["status"] for x in reports[-2:]] == [200, 304]


def test_nibble_packing_values(admin: TestClient):
    upload(admin)
    r = admin.get("/api/device/frame", headers=device_headers())
    arr = np.frombuffer(r.content, np.uint8)
    assert ((arr >> 4) <= 6).all() and ((arr & 0x0F) <= 6).all()


def test_show_next_queue(admin: TestClient):
    a = upload(admin, seed=1)
    b = upload(admin, seed=2)
    r = admin.get("/api/device/frame", headers=device_headers())
    first = int(r.headers["x-image-id"])
    other = b["id"] if first == a["id"] else a["id"]
    assert admin.post(f"/api/images/{other}/show-next").json() == [other]
    r = admin.get("/api/device/frame", headers=device_headers(r.headers["etag"]))
    assert r.status_code == 200 and int(r.headers["x-image-id"]) == other
    assert admin.get("/api/queue").json() == []


def test_disable_current_switches(admin: TestClient):
    a = upload(admin, seed=1)
    b = upload(admin, seed=2)
    r = admin.get("/api/device/frame", headers=device_headers())
    first = int(r.headers["x-image-id"])
    admin.patch(f"/api/images/{first}", json={"enabled": False})
    r = admin.get("/api/device/frame", headers=device_headers(r.headers["etag"]))
    assert r.status_code == 200 and int(r.headers["x-image-id"]) == ({a["id"], b["id"]} - {first}).pop()


def test_settings_reprocess_changes_etag(admin: TestClient, app):
    img = upload(admin)
    s = admin.get("/api/settings").json()
    s["rotation"] = 0
    assert admin.put("/api/settings", json=s).status_code == 200
    for _ in range(100):
        st = admin.get("/api/settings/reprocess").json()
        if not st["running"]:
            break
        time.sleep(0.05)
    new = admin.get("/api/images").json()[0]
    assert new["etag"] != img["etag"]


def test_settings_validation(admin: TestClient):
    s = admin.get("/api/settings").json()
    s["palette"] = ["#000000"]
    assert admin.put("/api/settings", json=s).status_code == 422


def test_calibration_image(admin: TestClient):
    r = admin.post("/api/images/calibration")
    assert r.status_code == 201 and r.json()["kind"] == "calibration"
    assert admin.get("/api/queue").json() == [r.json()["id"]]


def test_battery_calibration(admin: TestClient):
    upload(admin)
    admin.get("/api/device/frame?bat=3800", headers=device_headers())
    r = admin.post("/api/device/calibrate-battery", json={"measured_mv": 3990})
    assert r.status_code == 200 and r.json()["mv"] == 3990
    assert abs(admin.get("/api/settings").json()["battery_factor"] - 3990 / 3800) < 1e-3
    r = admin.get("/api/device/frame?bat=3800", headers=device_headers())
    assert r.headers["x-battery-factor"] == str(round(3990 / 3800 * 1000))


def test_unknown_api_is_404(admin: TestClient):
    assert admin.get("/api/nope").status_code == 404


def test_spa_fallback(tmp_path):
    from app.main import create_app

    static = tmp_path / "web"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<html>spa</html>")
    (static / "assets" / "app.js").write_text("console.log(1)")
    c = TestClient(create_app(make_config(tmp_path / "data", static)))
    assert "spa" in c.get("/gallery").text
    assert c.get("/assets/app.js").headers["cache-control"].startswith("public")
    assert c.get("/api/nope").status_code == 404
    assert "spa" in c.get("/../../etc/passwd").text


def test_device_tolerates_weird_values(admin):
    upload(admin)
    r = admin.get("/api/device/frame?bat=99999&rssi=12&awake=99999999&wake=" + "x" * 80, headers=device_headers())
    assert r.status_code == 200

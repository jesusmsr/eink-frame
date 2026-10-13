from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from .config import Config, load_config
from .db import init_engine
from .migrate import upgrade
from .routers import auth, device, images, settings
from .security import LoginLimiter
from .storage import Storage

log = logging.getLogger("eink")


def create_app(config: Config | None = None) -> FastAPI:
    cfg = config or load_config()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if not cfg.admin_password:
            log.warning("ADMIN_PASSWORD no está definido: no se podrá iniciar sesión")
        if not cfg.device_token:
            log.warning("DEVICE_TOKEN no está definido: el marco no podrá conectarse")
        yield

    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    init_engine(cfg.db_path)
    upgrade(cfg.db_path)

    app = FastAPI(
        title="E-Ink Frame",
        version=cfg.version,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.state.config = cfg
    app.state.storage = Storage(cfg.images_dir)
    app.state.login_limiter = LoginLimiter()

    app.add_middleware(
        SessionMiddleware,
        secret_key=cfg.secret_key,
        session_cookie="eink_session",
        max_age=cfg.session_days * 24 * 3600,
        same_site="lax",
        https_only=cfg.cookie_secure,
    )

    @app.get("/api/health", tags=["health"])
    def health() -> dict:
        return {"status": "ok", "version": cfg.version}

    app.include_router(auth.router)
    app.include_router(images.router)
    app.include_router(settings.router)
    app.include_router(device.router)

    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
    def api_not_found(path: str) -> JSONResponse:
        return JSONResponse({"detail": "No encontrado"}, status_code=404)

    _mount_spa(app, cfg.static_dir)
    return app


def _mount_spa(app: FastAPI, static_dir: Path | None) -> None:
    """Sirve la SPA compilada; cualquier ruta que no sea /api devuelve index.html."""
    if static_dir is None:
        return
    root = static_dir.resolve()
    index = root / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str, request: Request):
        candidate = (root / full_path).resolve()
        if full_path and candidate.is_file() and root in candidate.parents:
            cache = "public, max-age=31536000, immutable" if full_path.startswith("assets/") else "no-cache"
            return FileResponse(candidate, headers={"Cache-Control": cache})
        if not index.exists():
            raise HTTPException(404)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Request, status

from ..schemas import LoginIn, MeOut
from ..security import check_password, client_ip

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=MeOut)
def login(body: LoginIn, request: Request) -> MeOut:
    cfg = request.app.state.config
    limiter = request.app.state.login_limiter
    ip = client_ip(request)
    if limiter.blocked(ip):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Demasiados intentos. Espera 15 minutos.")
    if not cfg.admin_password:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ADMIN_PASSWORD no configurado en el servidor")
    if not check_password(body.password, cfg.admin_password):
        limiter.fail(ip)
        time.sleep(0.5)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Contraseña incorrecta")
    limiter.reset(ip)
    request.session.clear()
    request.session["admin"] = True
    return MeOut(authenticated=True, version=cfg.version)


@router.post("/logout", response_model=MeOut)
def logout(request: Request) -> MeOut:
    request.session.clear()
    return MeOut(authenticated=False, version=request.app.state.config.version)


@router.get("/me", response_model=MeOut)
def me(request: Request) -> MeOut:
    return MeOut(
        authenticated=request.session.get("admin") is True,
        version=request.app.state.config.version,
    )

from __future__ import annotations

import hmac
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


def client_ip(request: Request) -> str:
    # Detrás de Cloudflare la IP real llega en CF-Connecting-IP
    return (
        request.headers.get("cf-connecting-ip")
        or (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )


def require_admin(request: Request) -> None:
    if request.session.get("admin") is not True:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No autenticado")


def require_device(request: Request) -> None:
    token: str = request.app.state.config.device_token
    if not token:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "DEVICE_TOKEN no configurado")
    auth = request.headers.get("authorization", "")
    scheme, _, value = auth.partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(value.strip(), token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token de dispositivo inválido")


def check_password(given: str, expected: str) -> bool:
    if not expected:
        return False
    return hmac.compare_digest(given.encode(), expected.encode())


class LoginLimiter:
    """Máximo `limit` intentos fallidos por IP en `window` segundos."""

    def __init__(self, limit: int = 5, window: int = 15 * 60):
        self.limit, self.window = limit, window
        self._fails: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, ip: str, now: float) -> deque[float]:
        q = self._fails[ip]
        while q and now - q[0] > self.window:
            q.popleft()
        return q

    def blocked(self, ip: str) -> bool:
        with self._lock:
            return len(self._prune(ip, time.monotonic())) >= self.limit

    def fail(self, ip: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._prune(ip, now).append(now)

    def reset(self, ip: str) -> None:
        with self._lock:
            self._fails.pop(ip, None)

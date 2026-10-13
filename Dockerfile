# ---------- 1. Frontend ----------
FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# ---------- 2. Runtime ----------
FROM python:3.13-slim AS runtime

ARG APP_VERSION=dev
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data \
    STATIC_DIR=/app/web \
    APP_VERSION=${APP_VERSION} \
    TZ=Europe/Madrid \
    PUID=1000 \
    PGID=1000

WORKDIR /app/server
COPY server/requirements.txt ./
RUN pip install -r requirements.txt

COPY server/ ./
COPY --from=web /web/dist /app/web

# Por si el checkout en Windows convirtió los finales de línea a CRLF
RUN sed -i "s/\r$//" /app/server/entrypoint.sh && chmod +x /app/server/entrypoint.sh && mkdir -p /data

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

# Un solo worker: SQLite + procesado en segundo plano. --proxy-headers para Cloudflare/proxy.
ENTRYPOINT ["/app/server/entrypoint.sh"]
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*", "--no-server-header"]

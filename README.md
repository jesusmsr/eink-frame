# E-Ink Frame 2.0

Marco de fotos con **LOLIN D32 Pro** + **Waveshare 7.3" ACeP 7 colores (HAT F)**.
Un único contenedor Docker (`jesussr/eink-frame`) sirve el panel web y la API del marco.

```
eink-frame/
├── server/     FastAPI + SQLite: imágenes, cola, horario, informes de batería
├── web/        React + Vite + Tailwind: panel de control (móvil y escritorio)
├── firmware/   PlatformIO: firmware de bajo consumo del ESP32
├── Dockerfile  web + server en una sola imagen
└── compose.yaml  listo para Dockge
```

## Cómo funciona

1. Subes una foto desde el panel y la recortas. El servidor hace todo el trabajo pesado: orientación, ajuste de color y tramado (dithering) con la paleta real del panel. Lo guarda directamente en el **formato nativo del panel** (4 bits/píxel, 192.000 bytes).
2. El marco despierta y hace **una sola petición** a `GET /api/device/frame`, en la que informa de su batería, su señal WiFi y el tiempo que estuvo despierto la vez anterior.
   - `304`: no hay cambios y vuelve a dormir (~1–2 s despierto).
   - `200`: descarga los 192 KB a la PSRAM, **apaga el WiFi**, vuelca la imagen al panel y espera el refresco (~35 s) en light sleep.
3. El servidor decide cuánto duerme el marco (`X-Sleep-Seconds`). Así el intervalo, las horas de silencio o el modo de batería baja se cambian desde la web **sin reflashear**.

## Despliegue en Dockge (TrueNAS)

1. En Dockge, crea una pila nueva y pega `compose.yaml`.
2. En el apartado `.env` de la pila:
   ```env
   ADMIN_PASSWORD=una-contraseña-larga
   DEVICE_TOKEN=<genera uno: python -c "import secrets; print(secrets.token_urlsafe(32))">
   COOKIE_SECURE=false
   ```
3. Despliega. El panel queda en `http://IP-DEL-NAS:8080`.
4. **Cloudflare**: apunta tu hostname (p. ej. `app.jsanr.dev`) a `http://IP-DEL-NAS:8080`, ya sea con el túnel o con tu proxy. Si **solo** vas a entrar por HTTPS, pon `COOKIE_SECURE=true`.
5. El ESP32 **no** pasa por Cloudflare: habla directamente con `http://IP-DEL-NAS:8080`.

Los datos (SQLite, originales, versiones procesadas) quedan en `./data` dentro de la pila. Para hacer una copia de seguridad basta con copiar esa carpeta.

### Importar las fotos del sistema antiguo

Copia la carpeta `app/static/images` de la VM a `./data/import` y ejecuta:

```bash
docker exec -it eink-frame python -m app.cli import /data/import
```

Se ignoran los `*_processed.bmp` y se reprocesan los originales con el nuevo pipeline.

### Otros comandos

```bash
docker exec -it eink-frame python -m app.cli reprocess   # regenerar todas las imágenes
docker exec -it eink-frame python -m app.cli token       # generar un token aleatorio
```

## Construir y publicar la imagen

**Automático (recomendado)**: GitHub Actions (`.github/workflows/docker.yml`; si no está, cópialo desde `docs/ci/docker.yml`) ejecuta los tests y publica una imagen multi-arquitectura (amd64 + arm64) en Docker Hub.
- Cada push a `main` publica `jesussr/eink-frame:edge`.
- Cada tag `v2.0.0` publica `:2.0.0`, `:2.0` y `:latest`.

Necesita dos *secrets* en el repo de GitHub: `DOCKERHUB_USERNAME` (`jesussr`) y `DOCKERHUB_TOKEN` (créalo en Docker Hub → Account settings → Personal access tokens).

**A mano**:

```bash
docker build -t jesussr/eink-frame:2.0.0 -t jesussr/eink-frame:latest --build-arg APP_VERSION=2.0.0 .
docker push jesussr/eink-frame:2.0.0 && docker push jesussr/eink-frame:latest
```

## Firmware

```bash
cd firmware
cp include/config.example.h include/config.h   # WiFi, IP del NAS, DEVICE_TOKEN
pio run -e release -t upload                   # o -e debug para ver logs por serie
```

| Entorno | Para qué sirve |
|---|---|
| `release` | Uso normal, sin logs |
| `debug` | Logs por el puerto serie (115200) |
| `sleeptest` | Hiberna el panel, aparca los pines y duerme para siempre. Sirve para **medir el consumo en reposo** con el multímetro |

### Qué cambia respecto al firmware antiguo

| Antes | Ahora |
|---|---|
| BMP de 1,15 MB descargado en bloques de 128 B con `delay(1)` y guardado en SPIFFS | 192 KB nativos directos a PSRAM |
| Leía el BMP 5 veces desde la flash para pintarlo | Un único `writeNative()` |
| WiFi encendido durante los ~35 s de refresco | WiFi apagado antes de tocar la pantalla; refresco en light sleep |
| Reintentos cada 1–5 min si fallaba el WiFi o el servidor | Backoff de 5, 10, 20, 40 y 60 min |
| Sin medida de batería ni corte por tensión baja | Medida antes del WiFi; aviso en pantalla y parada por debajo del umbral crítico |
| Si un brownout reiniciaba la placa, volvía a empezar al instante (bucle) | Tras un reinicio anómalo duerme 30 min y lo informa al servidor |
| Pines flotando durante el deep sleep | Pines del HAT fijados a niveles definidos (`gpio_hold`) |
| DHCP y escaneo WiFi en cada ciclo | IP fija opcional, canal y BSSID recordados en la RTC |
| Siempre 30 min fijos | El servidor decide: intervalo, horas de silencio, ×2 con batería baja |

## Desarrollo local

```bash
# servidor
cd server && pip install -r requirements-dev.txt
DATA_DIR=./data ADMIN_PASSWORD=dev DEVICE_TOKEN=dev uvicorn app.main:create_app --factory --reload
python -m pytest -q

# web (proxy de /api a :8000)
cd web && npm install && npm run dev

# si cambias la API, regenera los tipos del frontend
cd server && python -m app.cli openapi openapi.json && cd ../web && npm run gen:api
```

La documentación interactiva de la API está en `/api/docs`.

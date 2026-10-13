#!/bin/sh
# Arranca como root solo para dejar /data con el propietario correcto (bind mounts
# creados por Docker/Dockge suelen ser de root) y luego baja a PUID:PGID.
set -e
PUID="${PUID:-1000}"
PGID="${PGID:-1000}"
if [ "$(id -u)" = "0" ]; then
  mkdir -p "${DATA_DIR:-/data}"
  if [ "$(stat -c %u "${DATA_DIR:-/data}")" != "$PUID" ]; then
    chown -R "$PUID:$PGID" "${DATA_DIR:-/data}"
  fi
  exec setpriv --reuid="$PUID" --regid="$PGID" --clear-groups "$@"
fi
exec "$@"

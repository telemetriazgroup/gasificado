#!/bin/sh
# Libera el puerto TCP en el host antes de levantar tcp_bridge.
# Uso: ./scripts/free_port.sh [PUERTO] [TIMEOUT_SEG]
set -eu

PORT="${1:-9970}"
MAX_WAIT="${2:-15}"

log() { echo "[free_port:$PORT] $*"; }

port_in_use() {
  if command -v ss >/dev/null 2>&1; then
    ss -tlnH "sport = :$PORT" 2>/dev/null | grep -q .
    return $?
  fi
  if command -v lsof >/dev/null 2>&1; then
    lsof -tiTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1
    return $?
  fi
  netstat -tln 2>/dev/null | grep -q ":${PORT} "
}

stop_docker_containers_on_port() {
  if ! command -v docker >/dev/null 2>&1 || [ ! -S /var/run/docker.sock ]; then
    return 0
  fi

  ids=$(docker ps -q --filter "publish=${PORT}" 2>/dev/null || true)
  if [ -n "$ids" ]; then
    log "Deteniendo contenedor(es) Docker que usan el puerto ${PORT}: ${ids}"
    docker stop --time 5 $ids >/dev/null 2>&1 || true
    sleep 1
  fi
}

kill_host_listeners() {
  if command -v fuser >/dev/null 2>&1; then
    if fuser "${PORT}/tcp" >/dev/null 2>&1; then
      log "Liberando procesos en ${PORT}/tcp (fuser)..."
      fuser -k "${PORT}/tcp" >/dev/null 2>&1 || true
      sleep 1
    fi
    return 0
  fi

  if command -v lsof >/dev/null 2>&1; then
    pids=$(lsof -tiTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null || true)
    if [ -n "$pids" ]; then
      log "Terminando proceso(s) en puerto ${PORT}: ${pids}"
      kill -TERM $pids >/dev/null 2>&1 || true
      sleep 1
      kill -KILL $pids >/dev/null 2>&1 || true
    fi
  fi
}

kill_legacy_tcp_script() {
  if command -v pgrep >/dev/null 2>&1; then
    pids=$(pgrep -f "tcp_g9070\\.py|bridge\\.py" 2>/dev/null || true)
    if [ -n "$pids" ]; then
      log "Deteniendo script TCP legacy: ${pids}"
      kill -TERM $pids >/dev/null 2>&1 || true
      sleep 1
      kill -KILL $pids >/dev/null 2>&1 || true
    fi
  fi
}

show_port_usage() {
  log "Procesos que aún usan el puerto ${PORT}:"
  if command -v ss >/dev/null 2>&1; then
    ss -tlnp "sport = :$PORT" 2>/dev/null || true
  elif command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true
  fi
}

attempt=1
while [ "$attempt" -le "$MAX_WAIT" ]; do
  if [ "$attempt" -eq 1 ]; then
    log "Iniciando limpieza del puerto ${PORT}..."
    stop_docker_containers_on_port
    kill_legacy_tcp_script
    kill_host_listeners
  fi

  if ! port_in_use; then
    log "Puerto ${PORT} libre."
    exit 0
  fi

  log "Esperando liberación (${attempt}/${MAX_WAIT})..."
  sleep 1

  if [ $((attempt % 3)) -eq 0 ]; then
    kill_host_listeners
  fi

  attempt=$((attempt + 1))
done

show_port_usage
log "ERROR: no se pudo liberar el puerto ${PORT}."
exit 1

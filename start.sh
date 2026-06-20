#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PORT="${TCP_PORT:-9970}"

chmod +x "$ROOT/scripts/free_port.sh"
/bin/sh "$ROOT/scripts/free_port.sh" "$PORT"

cd "$ROOT"
docker compose up -d --build "$@"

echo ""
echo "Servicios:"
echo "  Web UI:      http://localhost:8087/gasificado/"
echo "  Backend API: http://localhost:9070"
echo "  TCP:         puerto ${PORT}"

#!/usr/bin/env bash
# Start MARIS Q/A Helper stack (compose files from ./.env).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck source=compose_env.sh
source "$(dirname "$0")/compose_env.sh"
compose_env

echo "→ docker compose up (${COMPOSE[*]})"
compose_run up -d --build

echo "→ health"
sleep 2
curl -sf "http://127.0.0.1:${APP_PORT:-8088}/api/health" && echo

echo "App: http://127.0.0.1:${APP_PORT:-8088}"
echo "Logs: ${COMPOSE[*]} logs -f api"

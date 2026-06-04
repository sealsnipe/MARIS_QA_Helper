#!/usr/bin/env bash
# Start MARIS Q/A Helper stack (compose files from ./.env).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck source=compose_env.sh
source "$(dirname "$0")/compose_env.sh"
compose_env

echo "→ docker compose up (${COMPOSE[*]})"
if [[ -n "${OAUTH_AUTH_HOST_PATH:-}" ]]; then
  echo "  OAuth: ${OAUTH_AUTH_HOST_PATH}"
fi
compose_run up -d --build

echo "→ health"
sleep 3
api_cid="$(compose_run ps -q api 2>/dev/null | head -1 || true)"
if [[ -z "$api_cid" ]]; then
  echo "✗ API-Container läuft nicht — Logs:" >&2
  compose_run logs api --tail 40 >&2 || true
  exit 1
fi
port_map="$(docker port "$api_cid" 8088 2>/dev/null | head -1 || true)"
if [[ -z "$port_map" ]]; then
  echo "✗ Port 8088 nicht veröffentlicht — Container neu erstellen:" >&2
  echo "  ./scripts/stop.sh && ./scripts/start.sh" >&2
  compose_run logs api --tail 40 >&2 || true
  exit 1
fi

if ! curl -sf "http://127.0.0.1:${APP_PORT:-8088}/api/health"; then
  echo "" >&2
  echo "✗ Health-Check fehlgeschlagen — Logs:" >&2
  compose_run logs api --tail 40 >&2 || true
  exit 1
fi
echo ""

echo "App: http://127.0.0.1:${APP_PORT:-8088}"
echo "Logs: ${COMPOSE[*]} logs -f api"

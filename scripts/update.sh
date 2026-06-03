#!/usr/bin/env bash
# Update deployed instance after git pull (keeps ./data volume).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck source=compose_env.sh
source "$(dirname "$0")/compose_env.sh"
compose_env

echo "→ git pull"
git pull --ff-only

echo "→ rebuild & restart"
compose_run up -d --build

echo "→ health"
sleep 2
curl -sf "http://127.0.0.1:${APP_PORT:-8088}/api/health" && echo

echo "Done. Logs: ${COMPOSE[*]} logs -f api"

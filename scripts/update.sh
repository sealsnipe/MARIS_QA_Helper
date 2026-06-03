#!/usr/bin/env bash
# Update deployed instance after git pull (keeps ./data volume).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PROFILE="${DEPLOY_PROFILE:-prod}"
COMPOSE=(docker compose -f docker-compose.yml)
if [[ "$PROFILE" == "prod" ]]; then
  COMPOSE+=(-f docker-compose.prod.yml)
fi

echo "→ git pull"
git pull --ff-only

echo "→ rebuild & restart"
"${COMPOSE[@]}" up -d --build

echo "→ health"
sleep 2
curl -sf "http://127.0.0.1:${APP_PORT:-8088}/api/health" && echo

echo "Done. Logs: ${COMPOSE[*]} logs -f api"

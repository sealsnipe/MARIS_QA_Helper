#!/usr/bin/env bash
# Stop MARIS Q/A Helper stack (keeps ./data and .env).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck source=compose_env.sh
source "$(dirname "$0")/compose_env.sh"
compose_env

echo "→ docker compose down (${COMPOSE[*]})"
compose_run down

echo "Gestoppt. Daten in ./data bleiben erhalten."
echo "Start:  ./scripts/start.sh"
echo "Update: ./scripts/update.sh  (pull + rebuild, ohne manuelles stoppen nötig)"

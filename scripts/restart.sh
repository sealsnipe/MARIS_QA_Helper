#!/usr/bin/env bash
# Restart MARIS Q/A Helper stack (full stop + start, keeps ./data and .env).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

./scripts/stop.sh
./scripts/start.sh

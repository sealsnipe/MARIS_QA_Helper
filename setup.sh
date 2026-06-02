#!/usr/bin/env bash
# MARIS Q/A Helper — one-command first-time setup (env + credentials + optional docker start).
set -euo pipefail
cd "$(dirname "$0")"
exec python3 scripts/setup.py "$@"

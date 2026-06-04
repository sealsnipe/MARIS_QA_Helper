#!/usr/bin/env bash
# Run docker compose with the same file selection as start.sh (incl. OAuth env).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck source=compose_env.sh
source "$(dirname "$0")/compose_env.sh"
compose_env

exec compose_run "$@"

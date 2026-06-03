#!/usr/bin/env bash
# Run a second dev instance on port 8090 (native, no Docker required).
# Windows/WSL: open http://localhost:8090
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DEV_PORT="${DEV_PORT:-8090}"
QDRANT_PORT="${QDRANT_PORT:-6334}"
TOOLS="$ROOT/.tools"
QDRANT_BIN="$TOOLS/qdrant"
QDRANT_STORAGE="$ROOT/data-dev/qdrant_storage"
PID_DIR="$ROOT/data-dev/pids"
API_PID="$PID_DIR/api.pid"
QDRANT_PID="$PID_DIR/qdrant.pid"

mkdir -p "$ROOT/data-dev" "$QDRANT_STORAGE" "$PID_DIR" "$TOOLS"

if [[ ! -f .env.dev ]]; then
  if [[ -f .env ]]; then
    echo "→ .env.dev fehlt — kopiere aus .env und passe Ports/Pfade an"
    cp .env .env.dev
    sed -i "s|^DATABASE_URL=.*|DATABASE_URL=sqlite:///${ROOT}/data-dev/support_kb.sqlite3|" .env.dev
    sed -i "s|^QDRANT_URL=.*|QDRANT_URL=http://127.0.0.1:${QDRANT_PORT}|" .env.dev
    grep -q '^DEPLOY_PROFILE=' .env.dev || echo 'DEPLOY_PROFILE=dev' >> .env.dev
  else
    cp .env.dev.example .env.dev
    echo "→ .env.dev aus .env.dev.example — bitte OPENAI_API_KEY setzen"
  fi
fi

# shellcheck disable=SC1091
set -a
source .env.dev
set +a

export DATABASE_URL="${DATABASE_URL:-sqlite:///./data-dev/support_kb.sqlite3}"
export QDRANT_URL="${QDRANT_URL:-http://127.0.0.1:${QDRANT_PORT}}"

_ensure_qdrant_binary() {
  if [[ -x "$QDRANT_BIN" ]]; then
    return
  fi
  echo "→ Qdrant-Binary laden (einmalig) …"
  arch="$(uname -m)"
  case "$arch" in
    x86_64) qarch="x86_64-unknown-linux-gnu" ;;
    aarch64|arm64) qarch="aarch64-unknown-linux-gnu" ;;
    *) echo "Unsupported arch: $arch"; exit 1 ;;
  esac
  ver="1.18.1"
  tmp="$TOOLS/qdrant.tgz"
  curl -fsSL "https://github.com/qdrant/qdrant/releases/download/v${ver}/qdrant-${qarch}.tar.gz" -o "$tmp"
  tar -xzf "$tmp" -C "$TOOLS"
  rm -f "$tmp"
  chmod +x "$QDRANT_BIN"
}

_port_in_use() {
  ss -tln 2>/dev/null | grep -q ":$1 "
}

_start_qdrant() {
  if _port_in_use "$QDRANT_PORT"; then
    echo "○ Qdrant läuft bereits auf :${QDRANT_PORT}"
    return
  fi
  _ensure_qdrant_binary
  echo "→ Qdrant starten (:${QDRANT_PORT})"
  QDRANT__SERVICE__HTTP_PORT="$QDRANT_PORT" \
    QDRANT__STORAGE__STORAGE_PATH="$QDRANT_STORAGE" \
    nohup "$QDRANT_BIN" >"$ROOT/data-dev/qdrant.log" 2>&1 &
  echo $! >"$QDRANT_PID"
  for _ in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:${QDRANT_PORT}/" >/dev/null 2>&1; then
      echo "  ✓ Qdrant bereit"
      return
    fi
    sleep 0.5
  done
  echo "  ✗ Qdrant startet nicht — siehe data-dev/qdrant.log"
  exit 1
}

_start_api() {
  if _port_in_use "$DEV_PORT"; then
    echo "✗ Port ${DEV_PORT} belegt — anderer Dev-Server läuft schon?"
    echo "  Stoppen: ./scripts/dev_local.sh stop"
    exit 1
  fi
  echo "→ API starten (http://127.0.0.1:${DEV_PORT})"
  # shellcheck disable=SC1091
  set -a
  source "$ROOT/.env.dev"
  set +a
  export APP_PORT="$DEV_PORT"
  cd "$ROOT"
  nohup env PYTHONPATH=backend uvicorn app.main:app --host 0.0.0.0 --port "$DEV_PORT" --workers 1 --reload --reload-dir backend \
    >"$ROOT/data-dev/api.log" 2>&1 &
  echo $! >"$API_PID"
  for _ in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:${DEV_PORT}/api/health" >/dev/null 2>&1; then
      echo "  ✓ API bereit"
      return
    fi
    sleep 0.5
  done
  echo "  ✗ API startet nicht — siehe data-dev/api.log"
  tail -20 "$ROOT/data-dev/api.log" || true
  exit 1
}

_seed_if_empty() {
  if [[ -f "$ROOT/data-dev/support_kb.sqlite3" ]]; then
    return
  fi
  echo "→ Erstes Start — Seed (Kunden + Admin)"
  pw="${SEED_ADMIN_PASSWORD:-DevLocal123!}"
  cd "$ROOT"
  set -a
  source "$ROOT/.env.dev"
  set +a
  SEED_ADMIN_PASSWORD="$pw" PYTHONPATH=backend:scripts python3 scripts/seed_setup.py --profile dev \
    --email "${SEED_ADMIN_EMAIL:-admin@example.com}" --password "$pw"
  echo "  Login: ${SEED_ADMIN_EMAIL:-admin@example.com} / $pw"
}

_stop_one() {
  local pidfile="$1"
  local label="$2"
  if [[ -f "$pidfile" ]]; then
    local pid
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      echo "  gestoppt: $label (pid $pid)"
    fi
    rm -f "$pidfile"
  fi
}

cmd="${1:-start}"
case "$cmd" in
  start)
    _start_qdrant
    _seed_if_empty
    _start_api
    echo ""
    echo "Dev-Instanz: http://127.0.0.1:${DEV_PORT}  (Windows: http://localhost:${DEV_PORT})"
    echo "Logs: tail -f data-dev/api.log"
    echo "Stop: ./scripts/dev_local.sh stop"
    echo "Hinweis: --reload aktiv — Änderungen an .py-Dateien werden automatisch übernommen (nach kurzer Wartezeit)."
    ;;
  stop)
    _stop_one "$API_PID" "API"
    _stop_one "$QDRANT_PID" "Qdrant"
    echo "Dev-Instanz gestoppt."
    ;;
  status)
    curl -sf "http://127.0.0.1:${DEV_PORT}/api/health" && echo " API ok" || echo "API nicht erreichbar"
    curl -sf "http://127.0.0.1:${QDRANT_PORT}/" | head -c 80; echo
    ;;
  *)
    echo "Usage: $0 {start|stop|status}"
    exit 1
    ;;
esac

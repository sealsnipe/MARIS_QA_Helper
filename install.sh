#!/usr/bin/env bash
# Fresh Ubuntu bootstrap: system packages, Docker Engine, then setup wizard.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

INSTALL_ONLY=0
for arg in "$@"; do
  if [[ "$arg" == "--install-only" ]]; then
    INSTALL_ONLY=1
  fi
done

log() {
  printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"
}

log "=============================================="
log " MARIS Q/A Helper — Installation"
log " Frisches Ubuntu/WSL: Pakete + Docker + Setup"
log "=============================================="

if [[ ! -f /etc/os-release ]]; then
  log "Abbruch: /etc/os-release fehlt — nur Linux/Ubuntu/Debian unterstützt."
  exit 1
fi

# shellcheck disable=SC1091
source /etc/os-release
log "Plattform: ${PRETTY_NAME:-unknown}"

run_as_root() {
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    "$@"
  else
    env -u SUDO_ASKPASS sudo "$@"
  fi
}

# WSL: systemd helps docker service (Ubuntu 24.04+)
if grep -qi microsoft /proc/version 2>/dev/null; then
  if [[ ! -f /etc/wsl.conf ]] || ! grep -q '^systemd=true' /etc/wsl.conf 2>/dev/null; then
    log "WSL: aktiviere systemd in /etc/wsl.conf (einmalig, WSL-Neustart danach ggf. nötig)"
    run_as_root tee /etc/wsl.conf >/dev/null <<'EOF'
[boot]
systemd=true
EOF
  fi
fi

log "=== Schritt 1/3: System-Pakete (git, python3, curl) ==="
run_as_root apt-get update
run_as_root apt-get install -y git python3 curl ca-certificates
log "Schritt 1/3 fertig."

log "=== Schritt 2/3: Docker Engine + Compose (kann 5–15 Min. dauern) ==="
python3 scripts/docker_preflight.py --install
python3 scripts/start_docker.py
python3 scripts/docker_preflight.py --check
log "Schritt 2/3 fertig."

if [[ "$INSTALL_ONLY" -eq 1 ]]; then
  log "=== --install-only: Setup-Wizard übersprungen ==="
  log "Weiter: ./setup.sh  (Credentials interaktiv auf dieser Maschine)"
  exit 0
fi

log "=== Schritt 3/3: Credentials & App ==="
if printf '%s\n' "$@" | grep -q -- '--non-interactive'; then
  log "Non-interactive — Key/Auth aus Parametern oder Env."
else
  log "Interaktiv — OpenAI API-Key und Chat-Auth werden jetzt abgefragt."
fi

exec python3 scripts/setup.py --skip-docker-check "$@"

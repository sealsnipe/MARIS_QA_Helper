#!/usr/bin/env bash
# Fresh Ubuntu bootstrap: system packages, Docker Engine, then setup wizard.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

INSTALL_ONLY=0
CONTINUE=0
WSL_CONF_CHANGED=0
for arg in "$@"; do
  case "$arg" in
    --install-only) INSTALL_ONLY=1 ;;
    --continue) CONTINUE=1 ;;
  esac
done

log() {
  printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"
}

log "=============================================="
log " MARIS Q/A Helper — Installation"
if [[ "$CONTINUE" -eq 1 ]]; then
  log " Fortsetzen nach WSL-Neustart / Docker"
else
  log " Frisches Ubuntu/WSL: Pakete + Docker + Setup"
fi
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

finish_install_only() {
  log "=== Install-Phase fertig (Setup noch ausstehend) ==="
  log "Weiter:"
  log "  ./install.sh --continue    # nach WSL-Neustart oder wenn Docker läuft"
  log "  ./setup.sh                 # nur Credentials + Compose (Docker muss ready sein)"
}

# WSL: systemd helps docker service (Ubuntu 24.04+)
if grep -qi microsoft /proc/version 2>/dev/null; then
  if [[ ! -f /etc/wsl.conf ]] || ! grep -q '^systemd=true' /etc/wsl.conf 2>/dev/null; then
    log "WSL: aktiviere systemd in /etc/wsl.conf (WSL-Neustart danach nötig)"
    run_as_root tee /etc/wsl.conf >/dev/null <<'EOF'
[boot]
systemd=true
EOF
    WSL_CONF_CHANGED=1
  fi
fi

if [[ "$CONTINUE" -eq 1 ]]; then
  log "=== Fortsetzen: Docker prüfen/starten ==="
  set +e
  python3 scripts/start_docker.py
  START_RC=$?
  set -e
  if [[ "$START_RC" -eq 2 ]]; then
    log "Abbruch: WSL-Neustart noch nötig (siehe Hinweise oben)."
    finish_install_only
    exit 0
  fi
  if [[ "$START_RC" -ne 0 ]]; then
    exit "$START_RC"
  fi
  python3 scripts/docker_preflight.py --check-bootstrap
  log "Docker bereit."
else
log "=== Schritt 1/3: System-Pakete (git, python3, curl) ==="
run_as_root apt-get update
run_as_root apt-get install -y git python3 python3-pip curl ca-certificates
if ! python3 -c "import httpx" 2>/dev/null; then
  log "→ Python: httpx für OAuth-Setup (Host, optional)"
  python3 -m pip install --user httpx oauth-codex --break-system-packages 2>/dev/null \
    || python3 -m pip install --user httpx oauth-codex
fi
log "Schritt 1/3 fertig."

  log "=== Schritt 2/3: Docker Engine + Compose (kann 5–15 Min. dauern) ==="
  python3 scripts/docker_preflight.py --install
  set +e
  python3 scripts/start_docker.py
  START_RC=$?
  set -e

  if [[ "$START_RC" -eq 2 ]]; then
    log "Schritt 2/3: Docker installiert — WSL-Neustart nötig bevor der Daemon startet."
    finish_install_only
    exit 0
  fi
  if [[ "$START_RC" -ne 0 ]]; then
    exit "$START_RC"
  fi

  if ! python3 scripts/docker_preflight.py --check-bootstrap; then
    if [[ "$WSL_CONF_CHANGED" -eq 1 ]]; then
      log "Hinweis: systemd gerade aktiviert — ggf. WSL-Neustart, dann ./install.sh --continue"
      finish_install_only
      exit 0
    fi
    log "Abbruch: Docker-Bootstrap-Check fehlgeschlagen (siehe Status oben)."
    log "Workaround: newgrp docker && ./setup.sh"
    exit 1
  fi
  log "Schritt 2/3 fertig."
fi

if [[ "$INSTALL_ONLY" -eq 1 ]]; then
  log "=== --install-only: Setup-Wizard übersprungen ==="
  finish_install_only
  exit 0
fi

log "=== Schritt 3/3: Credentials & App ==="
if printf '%s\n' "$@" | grep -q -- '--non-interactive'; then
  log "Non-interactive — Key/Auth aus Parametern oder Env."
else
  log "Interaktiv — OpenAI API-Key und Chat-Auth werden jetzt abgefragt."
fi

# Gruppe docker in Session aktivieren wenn konfiguriert (usermod ohne Relogin)
docker_gid="$(getent group docker 2>/dev/null | cut -d: -f3 || true)"
if [[ -n "$docker_gid" ]] && id -nG | grep -qw docker && [[ " $(id -G) " != *" ${docker_gid} "* ]]; then
  log "Aktiviere Gruppe docker in dieser Shell (sg docker) …"
  quoted=()
  for arg in "$@"; do quoted+=("$(printf '%q' "$arg")"); done
  exec sg docker -c "cd $(printf '%q' "$ROOT") && exec python3 scripts/setup.py --skip-docker-check ${quoted[*]}"
fi

exec python3 scripts/setup.py --skip-docker-check "$@"

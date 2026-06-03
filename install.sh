#!/usr/bin/env bash
# Fresh Ubuntu bootstrap: system packages, Docker Engine, then interactive setup wizard.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "=============================================="
echo " MARIS Q/A Helper — Installation"
echo " Frisches Ubuntu/WSL: Pakete + Docker + Setup"
echo "=============================================="
echo

if [[ ! -f /etc/os-release ]]; then
  echo "Abbruch: /etc/os-release fehlt — nur Linux/Ubuntu/Debian unterstützt." >&2
  exit 1
fi

# shellcheck disable=SC1091
source /etc/os-release
if [[ "${ID:-}" != "ubuntu" && "${ID:-}" != "debian" ]]; then
  echo "Warnung: getestet für Ubuntu/Debian, erkannt: ${ID:-unknown}" >&2
fi

run_as_root() {
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    "$@"
  else
    # Cursor-Agent: SUDO_ASKPASS blockiert -S — explizit deaktivieren.
    env -u SUDO_ASKPASS sudo "$@"
  fi
}

echo "=== Schritt 1/3: System-Pakete (git, python3, curl) ==="
run_as_root apt-get update -qq
run_as_root apt-get install -y -qq git python3 curl ca-certificates

echo
echo "=== Schritt 2/3: Docker Engine + Compose ==="
python3 scripts/docker_preflight.py --install
python3 scripts/start_docker.py
python3 scripts/docker_preflight.py --check

echo
echo "=== Schritt 3/3: Credentials & App (interaktiv) ==="
echo "  → OpenAI API-Key und Chat-Auth werden jetzt abgefragt (nicht im Git)."
echo

exec python3 scripts/setup.py --skip-docker-check "$@"

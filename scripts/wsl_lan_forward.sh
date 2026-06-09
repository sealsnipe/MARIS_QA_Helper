#!/usr/bin/env bash
# Forward dev port from Windows LAN IP to this WSL2 instance (portproxy + firewall).
# Requires: Windows PowerShell, UAC approval on first setup.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PS1_WIN="$(wslpath -w "$ROOT/scripts/wsl_lan_forward.ps1")"
DEV_PORT="${DEV_PORT:-8090}"
ACTION="${1:-setup}"

if [[ ! -f /proc/version ]] || ! grep -qi microsoft /proc/version 2>/dev/null; then
  echo "Dieses Skript ist für WSL2 + Windows gedacht." >&2
  exit 1
fi

case "$ACTION" in
  setup|remove|status) ;;
  *)
    echo "Usage: $0 [setup|remove|status]" >&2
    echo "  setup   — Port ${DEV_PORT} auf WSL umbiegen (Default, UAC)" >&2
    echo "  remove  — Weiterleitung + Firewall-Regel entfernen" >&2
    echo "  status  — Aktuelle Regeln und LAN-URLs anzeigen" >&2
    exit 1
    ;;
esac

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PS1_WIN" -Action "$ACTION" -Port "$DEV_PORT"

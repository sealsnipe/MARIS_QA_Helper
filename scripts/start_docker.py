#!/usr/bin/env python3
"""Start Docker daemon on Ubuntu/WSL after install (best-effort)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from docker_preflight import (
    check_docker,
    is_wsl,
    systemd_is_running,
    wsl_needs_restart_for_systemd,
)

# Exit 2: WSL/systemd needs restart before daemon can run — install can continue later.
NEEDS_WSL_RESTART = 2


def _log(msg: str) -> None:
    print(msg, flush=True)


def _run(cmd: list[str]) -> int:
    return subprocess.run(cmd, check=False).returncode


def _daemon_reachable() -> bool:
    status = check_docker()
    return status.daemon_ok or status.daemon_ok_sudo


def _try_start_daemon() -> None:
    if shutil.which("systemctl") and systemd_is_running():
        if os.geteuid() == 0:
            _run(["systemctl", "enable", "docker"])
            _run(["systemctl", "start", "docker"])
        else:
            subprocess.run(
                ["env", "-u", "SUDO_ASKPASS", "sudo", "systemctl", "enable", "docker"],
                check=False,
            )
            subprocess.run(
                ["env", "-u", "SUDO_ASKPASS", "sudo", "systemctl", "start", "docker"],
                check=False,
            )
        return

    if shutil.which("service"):
        if os.geteuid() == 0:
            _run(["service", "docker", "start"])
        else:
            subprocess.run(["env", "-u", "SUDO_ASKPASS", "sudo", "service", "docker", "start"], check=False)


def _try_dockerd_background() -> None:
    if not shutil.which("dockerd"):
        return
    _log("  → Fallback: dockerd im Hintergrund starten …")
    log_path = Path("/var/log/dockerd-maris.log")
    with log_path.open("a", encoding="utf-8") as handle:
        subprocess.Popen(
            ["dockerd"],
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )


def _wait_for_daemon(*, seconds: int, label: str) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if _daemon_reachable():
            return True
        time.sleep(2)
        _log(f"  … {label}")
    return False


def _print_wsl_restart_hint() -> None:
    distro = os.environ.get("WSL_DISTRO_NAME", "<distro>")
    _log("")
    _log("  ══ WSL-Neustart nötig (systemd wurde aktiviert) ══")
    _log("  PowerShell (Windows):")
    _log("    wsl --shutdown")
    _log(f"    wsl -d {distro}")
    _log("  Dann in WSL:")
    _log("    cd ~/projects/MARIS_QA_Helper   # oder dein Clone-Pfad")
    _log("    ./install.sh --continue")
    _log("  Alternative: Docker Desktop + WSL-Integration für diese Distro.")


def main() -> None:
    status = check_docker()
    if status.daemon_ok:
        _log("  ✓ Docker-Daemon läuft bereits")
        return
    if status.daemon_ok_sudo and status.daemon_permission_denied:
        _log("  ✓ Docker-Daemon läuft (Gruppe docker — newgrp docker für Setup)")
        return

    if wsl_needs_restart_for_systemd():
        _log("  ⚠ WSL: systemd=true gesetzt, systemd läuft noch nicht in dieser Session.")
        _print_wsl_restart_hint()
        sys.exit(NEEDS_WSL_RESTART)

    _log("  → Docker-Daemon starten …")
    _try_start_daemon()

    wait_seconds = 30 if is_wsl() and not systemd_is_running() else 90
    if _wait_for_daemon(seconds=wait_seconds, label="warte auf Docker-Daemon"):
        refreshed = check_docker()
        if refreshed.daemon_ok:
            _log("  ✓ Docker-Daemon gestartet")
        else:
            _log("  ✓ Docker-Daemon gestartet (sudo)")
        return

    if is_wsl() and wsl_needs_restart_for_systemd():
        _print_wsl_restart_hint()
        sys.exit(NEEDS_WSL_RESTART)

    if is_wsl() and not systemd_is_running():
        _try_dockerd_background()
        if _wait_for_daemon(seconds=30, label="warte auf dockerd"):
            _log("  ✓ Docker-Daemon gestartet (dockerd)")
            return

    if is_wsl():
        _log(
            "  ✗ Docker-Daemon nicht erreichbar.\n"
            "    WSL: Docker Desktop starten + WSL-Integration für diese Distro,\n"
            "    oder: sudo service docker start / sudo dockerd"
        )
        _print_wsl_restart_hint()
    else:
        _log("  ✗ Docker-Daemon startet nicht — prüfe: sudo systemctl status docker")
    sys.exit(1)


if __name__ == "__main__":
    main()

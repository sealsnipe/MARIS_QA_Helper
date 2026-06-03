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
from docker_preflight import check_docker, is_wsl


def _log(msg: str) -> None:
    print(msg, flush=True)


def _run(cmd: list[str]) -> int:
    return subprocess.run(cmd, check=False).returncode


def _try_start_daemon() -> None:
    if shutil.which("systemctl"):
        try:
            if subprocess.run(["systemctl", "is-system-running"], capture_output=True, check=False).returncode == 0:
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
        except OSError:
            pass

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


def main() -> None:
    if check_docker().daemon_ok:
        _log("  ✓ Docker-Daemon läuft bereits")
        return

    _log("  → Docker-Daemon starten …")
    _try_start_daemon()

    deadline = time.time() + 90
    while time.time() < deadline:
        if check_docker().daemon_ok:
            _log("  ✓ Docker-Daemon gestartet")
            return
        time.sleep(2)
        _log("  … warte auf Docker-Daemon")

    if is_wsl():
        _try_dockerd_background()
        deadline = time.time() + 60
        while time.time() < deadline:
            if check_docker().daemon_ok:
                _log("  ✓ Docker-Daemon gestartet (dockerd)")
                return
            time.sleep(2)

    if is_wsl():
        _log(
            "  ✗ Docker-Daemon nicht erreichbar.\n"
            "    WSL: Docker Desktop starten + WSL-Integration für diese Distro,\n"
            "    oder: sudo service docker start / sudo dockerd"
        )
    else:
        _log("  ✗ Docker-Daemon startet nicht — prüfe: sudo systemctl status docker")
    sys.exit(1)


if __name__ == "__main__":
    main()

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


def _run(cmd: list[str]) -> int:
    return subprocess.run(cmd, check=False).returncode


def main() -> None:
    if check_docker().daemon_ok:
        print("  ✓ Docker-Daemon läuft bereits")
        return

    print("  → Docker-Daemon starten …")

    if shutil.which("systemctl") and _run(["systemctl", "is-system-running"]) == 0:
        if os.geteuid() == 0:
            _run(["systemctl", "enable", "--now", "docker"])
        else:
            subprocess.run(["env", "-u", "SUDO_ASKPASS", "sudo", "systemctl", "enable", "--now", "docker"], check=False)
    elif shutil.which("service"):
        if os.geteuid() == 0:
            _run(["service", "docker", "start"])
        else:
            subprocess.run(["env", "-u", "SUDO_ASKPASS", "sudo", "service", "docker", "start"], check=False)

    for _ in range(10):
        if check_docker().daemon_ok:
            print("  ✓ Docker-Daemon gestartet")
            return
        time.sleep(1)

    if is_wsl():
        print(
            "  ⚠ Docker-Daemon nicht erreichbar.\n"
            "    WSL: Docker Desktop starten + WSL-Integration für diese Distro aktivieren,\n"
            "    oder erneut: sudo service docker start"
        )
    else:
        print("  ⚠ Docker-Daemon startet nicht — prüfe: sudo systemctl status docker")
    sys.exit(1)


if __name__ == "__main__":
    main()

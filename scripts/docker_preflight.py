#!/usr/bin/env python3
"""Docker / Compose preflight checks and optional install (Ubuntu/Debian)."""

from __future__ import annotations

import getpass
import grp
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


MIN_DOCKER_VERSION = (20, 10, 0)
MIN_COMPOSE_VERSION = (2, 20, 0)


@dataclass
class DockerStatus:
    docker_bin: bool = False
    docker_version: tuple[int, int, int] | None = None
    compose_ok: bool = False
    compose_plugin: bool = False
    compose_version: tuple[int, int, int] | None = None
    daemon_ok: bool = False
    in_docker_group: bool = False
    platform_id: str = "unknown"
    platform_version: str = ""
    wsl: bool = False
    version_ok: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return (
            self.docker_bin
            and self.compose_ok
            and self.daemon_ok
            and self.in_docker_group
            and self.version_ok
        )

    @property
    def meets_minimum_versions(self) -> bool:
        return self.version_ok

    @property
    def installable(self) -> bool:
        return self.platform_id in {"ubuntu", "debian"} and shutil.which("apt-get") is not None


def _run(cmd: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def _parse_version(text: str) -> tuple[int, int, int] | None:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def is_wsl() -> bool:
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        return "microsoft" in Path("/proc/version").read_text(encoding="utf-8").lower()
    except OSError:
        return False


def read_os_release() -> dict[str, str]:
    data: dict[str, str] = {}
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                data[key] = value.strip().strip('"')
    except OSError:
        pass
    return data


def user_in_docker_group(username: str | None = None) -> bool:
    username = username or getpass.getuser()
    try:
        grp.getgrnam("docker")
    except KeyError:
        return False
    if username == getpass.getuser():
        try:
            return grp.getgrnam("docker").gr_gid in os.getgroups()
        except OSError:
            pass
    result = _run(["id", "-nG", username])
    if result.returncode != 0:
        return False
    return "docker" in result.stdout.split()


def _version_at_least(found: tuple[int, int, int] | None, minimum: tuple[int, int, int]) -> bool:
    return found is not None and found >= minimum


def check_docker() -> DockerStatus:
    status = DockerStatus()
    os_release = read_os_release()
    status.platform_id = os_release.get("ID", "unknown").lower()
    status.platform_version = os_release.get("VERSION_ID", "")
    status.wsl = is_wsl()

    status.docker_bin = shutil.which("docker") is not None
    if status.docker_bin:
        engine = _run(["docker", "version", "--format", "{{.Server.Version}}"])
        if engine.returncode != 0:
            engine = _run(["docker", "version", "--format", "{{.Client.Version}}"])
        if engine.returncode == 0:
            status.docker_version = _parse_version(engine.stdout)

        result = _run(["docker", "compose", "version"])
        if result.returncode == 0:
            status.compose_ok = True
            status.compose_plugin = True
            status.compose_version = _parse_version(result.stdout + result.stderr)
        else:
            legacy = _run(["docker-compose", "version"])
            if legacy.returncode == 0:
                status.compose_ok = True
                status.compose_version = _parse_version(legacy.stdout + legacy.stderr)
                status.notes.append(
                    "Legacy docker-compose ohne Compose-Plugin — bitte docker-compose-plugin installieren."
                )

        info = _run(["docker", "info"])
        status.daemon_ok = info.returncode == 0
        if not status.daemon_ok:
            if status.wsl:
                status.notes.append(
                    "Docker-Daemon nicht erreichbar. WSL: Docker Desktop WSL-Integration "
                    "aktivieren oder 'sudo service docker start'."
                )
            else:
                status.notes.append("Docker-Daemon läuft nicht — ggf. sudo systemctl start docker.")

    status.in_docker_group = os.geteuid() == 0 or user_in_docker_group()
    if status.docker_bin and not status.in_docker_group:
        status.notes.append("Nutzer nicht in Gruppe 'docker' — nach Install neu anmelden oder 'newgrp docker'.")

    engine_ok = _version_at_least(status.docker_version, MIN_DOCKER_VERSION)
    compose_ok = status.compose_plugin and _version_at_least(status.compose_version, MIN_COMPOSE_VERSION)
    status.version_ok = engine_ok and compose_ok

    if status.docker_bin and status.docker_version and not engine_ok:
        status.notes.append(
            f"Docker Engine {'.'.join(map(str, status.docker_version))} zu alt — "
            f"Minimum {'.'.join(map(str, MIN_DOCKER_VERSION))}."
        )
    if status.compose_ok and status.compose_version and not compose_ok:
        status.notes.append(
            f"docker compose {'.'.join(map(str, status.compose_version))} zu alt — "
            f"Minimum {'.'.join(map(str, MIN_COMPOSE_VERSION))} (Plugin erforderlich)."
        )

    return status


def assert_docker_ready(status: DockerStatus, *, context: str = "Setup") -> None:
    if status.ready:
        return
    print(f"\n  ✗ {context}: Docker-Anforderungen nicht erfüllt.")
    print_docker_status(status)
    if status.docker_bin and status.compose_ok and not status.version_ok:
        print(
            f"\n  Abbruch: Docker/Compose-Version unter Minimum "
            f"(Engine ≥ {'.'.join(map(str, MIN_DOCKER_VERSION))}, "
            f"Compose-Plugin ≥ {'.'.join(map(str, MIN_COMPOSE_VERSION))})."
        )
        print("  Upgrade: python3 scripts/docker_preflight.py --install")
    raise SystemExit(1)


def print_docker_status(status: DockerStatus) -> None:
    if status.docker_bin:
        print("  ✓ docker CLI")
    else:
        print("  ✗ docker CLI fehlt")

    if status.compose_ok:
        version = ".".join(map(str, status.compose_version)) if status.compose_version else "?"
        kind = "Plugin" if status.compose_plugin else "legacy"
        print(f"  ✓ docker compose ({version}, {kind})")
    else:
        print("  ✗ docker compose fehlt")

    if status.docker_version:
        print(f"  ○ Docker Engine {'.'.join(map(str, status.docker_version))}")

    if status.daemon_ok:
        print("  ✓ Docker-Daemon erreichbar")
    elif status.docker_bin:
        print("  ✗ Docker-Daemon nicht erreichbar")

    if status.in_docker_group:
        print("  ✓ Nutzer in Gruppe docker")
    elif status.docker_bin:
        print("  ⚠ Nutzer nicht in Gruppe docker")

    if status.wsl:
        print("  ○ WSL erkannt")
    if status.platform_id != "unknown":
        print(f"  ○ Plattform: {status.platform_id} {status.platform_version}".rstrip())

    for note in status.notes:
        print(f"  ⚠ {note}")


def _sudo_cmd(args: list[str]) -> list[str]:
    if os.geteuid() == 0:
        return args
    sudo = shutil.which("sudo")
    if not sudo:
        raise RuntimeError("sudo nicht gefunden — Installation braucht root-Rechte.")
    return [sudo, *args]


def _sudo_run(args: list[str]) -> None:
    env = os.environ.copy()
    env["DEBIAN_FRONTEND"] = "noninteractive"
    subprocess.run(_sudo_cmd(args), check=True, env=env)


def install_docker_engine(*, force: bool = False) -> None:
    """Install Docker Engine + Compose plugin on Ubuntu/Debian via official APT repo."""
    status = check_docker()
    if not force and status.docker_bin and status.compose_plugin and status.version_ok:
        print("\n  ○ Docker bereits installiert (Version ok) — übersprungen.")
        return
    if not force and status.docker_bin and status.compose_ok and not status.version_ok:
        print("\n  Docker/Compose zu alt — Upgrade via apt …")

    if not status.installable:
        raise RuntimeError(
            f"Automatische Installation nur für Ubuntu/Debian (apt). "
            f"Erkannt: {status.platform_id}. Siehe https://docs.docker.com/engine/install/"
        )

    distro = status.platform_id
    repo_name = "ubuntu" if distro == "ubuntu" else "debian"
    os_release = read_os_release()
    codename = os_release.get("VERSION_CODENAME", "")
    if not codename:
        raise RuntimeError("VERSION_CODENAME in /etc/os-release fehlt.")

    print("\n=== Docker installieren (sudo nötig) ===\n")
    print(f"  Quelle: Docker APT ({repo_name}, {codename})")

    arch = _run(["dpkg", "--print-architecture"], check=True).stdout.strip()
    keyring = Path("/etc/apt/keyrings/docker.asc")
    list_file = Path("/etc/apt/sources.list.d/docker.list")
    list_line = (
        f"deb [arch={arch} signed-by={keyring}] "
        f"https://download.docker.com/linux/{repo_name} {codename} stable\n"
    )

    _sudo_run(["apt-get", "update", "-qq"])
    print("  → apt: ca-certificates, curl …", flush=True)
    _sudo_run(["apt-get", "install", "-y", "ca-certificates", "curl"])
    _sudo_run(["install", "-m", "0755", "-d", str(keyring.parent)])

    gpg = _run(
        ["curl", "-fsSL", f"https://download.docker.com/linux/{repo_name}/gpg"],
        check=True,
    )
    tmp_gpg = Path("/tmp/docker.gpg.asc")
    tmp_gpg.write_text(gpg.stdout, encoding="utf-8")
    _sudo_run(["cp", str(tmp_gpg), str(keyring)])
    _sudo_run(["chmod", "a+r", str(keyring)])
    tmp_gpg.unlink(missing_ok=True)

    tmp_list = Path("/tmp/docker.list")
    tmp_list.write_text(list_line, encoding="utf-8")
    _sudo_run(["cp", str(tmp_list), str(list_file)])
    tmp_list.unlink(missing_ok=True)

    _sudo_run(["apt-get", "update", "-qq"])
    _sudo_run(
        [
            "apt-get",
            "install",
            "-y",
            "docker-ce",
            "docker-ce-cli",
            "containerd.io",
            "docker-buildx-plugin",
            "docker-compose-plugin",
        ]
    )

    user = getpass.getuser()
    if user != "root":
        _sudo_run(["usermod", "-aG", "docker", user])

    if not status.wsl and shutil.which("systemctl"):
        _sudo_run(["systemctl", "enable", "--now", "docker"])

    print("  ✓ Docker-Pakete installiert")
    if not user_in_docker_group():
        print("\n  → Gruppe 'docker' gesetzt. Session neu starten oder: newgrp docker")


def ensure_docker(
    *,
    interactive: bool = True,
    auto_install: bool = False,
    skip_install: bool = False,
) -> DockerStatus:
    """Check Docker; optionally offer or run installation."""
    status = check_docker()
    if status.ready:
        print("\n  ○ Docker bereit (Version geprüft, übersprungen).")
        return status

    if skip_install:
        return status

    wants_install = auto_install
    can_install = status.installable

    if status.wsl and not status.docker_bin:
        print("\n  WSL ohne Docker:")
        print("    A) Docker Desktop (Windows) + WSL-Integration — empfohlen für Dev")
        print("    B) Docker Engine in WSL installieren (sudo, dieses Script)")
        if interactive and not auto_install:
            choice = input("\n  Docker Engine in WSL installieren? [j/N]: ").strip().lower()
            wants_install = choice in {"j", "ja", "y", "yes"}
        elif not auto_install:
            return status

    needs_install = not status.ready and (
        not status.docker_bin or not status.compose_plugin or not status.version_ok
    )
    if needs_install and can_install and (wants_install or (interactive and _prompt_install())):
        try:
            install_docker_engine(force=not status.version_ok and status.docker_bin)
        except (RuntimeError, subprocess.CalledProcessError) as exc:
            print(f"  ✗ Installation fehlgeschlagen: {exc}")
            return check_docker()
        status = check_docker()
        if status.docker_bin and not status.daemon_ok and status.wsl:
            print("\n  Unter WSL: Docker Desktop starten oder 'sudo service docker start'")
    elif needs_install and not wants_install:
        print("\n  Manuelle Installation: https://docs.docker.com/engine/install/")

    return status


def _prompt_install() -> bool:
    while True:
        raw = input("\n  Docker Engine + Compose jetzt installieren (sudo)? [j/N]: ").strip().lower()
        if raw in {"", "n", "nein", "no"}:
            return False
        if raw in {"j", "ja", "y", "yes"}:
            return True
        print("  Bitte j oder n eingeben.")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Docker preflight / optional install")
    parser.add_argument("--check", action="store_true", help="Nur prüfen (Exit 1 wenn nicht ready)")
    parser.add_argument("--install", action="store_true", help="Pakete installieren (sudo)")
    args = parser.parse_args()

    if args.install:
        install_docker_engine()
        status = check_docker()
    else:
        status = ensure_docker(
            interactive=not args.check,
            auto_install=False,
            skip_install=args.check,
        )

    print()
    print_docker_status(status)

    if args.check and not status.ready:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

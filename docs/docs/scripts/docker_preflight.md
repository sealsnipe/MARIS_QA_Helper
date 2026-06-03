# `scripts/docker_preflight.py`

**Quellpfad:** `scripts/docker_preflight.py`

## Zweck und logischer Aufbau

Prüft **Docker Engine, Compose-Plugin, Daemon-Erreichbarkeit, Gruppenmitgliedschaft und Mindestversionen**; optional Installation auf Ubuntu/Debian per offiziellem APT-Repo. Zentral für `setup.py`, `install.sh` und `start_docker.py`.

Lesereihenfolge: Konstanten `MIN_*` → Dataclass `DockerStatus` → Low-Level-Helfer (`_run`, `_parse_version`, WSL/OS) → `check_docker` → Ausgabe/Assert → Install (`install_docker_engine`) → `ensure_docker` → `main` mit argparse.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `subprocess`, `shutil`, `grp`, `getpass`, `/etc/os-release`, `/proc/version`, `/etc/wsl.conf`
- **Wird genutzt von:** `scripts/setup.py`, `scripts/start_docker.py`, `install.sh` (indirekt)
- **CLI:** `python3 scripts/docker_preflight.py [--check|--check-bootstrap|--install]`
- **Extern:** Docker APT-Repo, `docker compose`, `sudo`

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `MIN_DOCKER_VERSION` | `tuple` | `(20, 10, 0)` |
| `MIN_COMPOSE_VERSION` | `tuple` | `(2, 20, 0)` |
| `DockerStatus` | `@dataclass` | Aggregierter Prüfstatus (siehe Properties unten) |

### Klasse `DockerStatus`

| Feld / Property | Beschreibung |
|---|---|
| `docker_bin`, `docker_version` | CLI vorhanden und Version |
| `compose_ok`, `compose_plugin`, `compose_version` | Compose erkannt (Plugin bevorzugt) |
| `daemon_ok`, `daemon_ok_sudo`, `daemon_permission_denied` | `docker info` |
| `in_docker_group`, `docker_group_in_session` | Gruppe `docker` |
| `platform_id`, `platform_version`, `wsl` | OS-Kontext |
| `version_ok`, `notes` | Mindestversion + Hinweise |
| `ready` | Property: bin + compose + Daemon + Gruppe + Version |
| `bootstrap_ready` | Install-Phase: Daemon via sudo ok, Gruppe in Session optional |
| `meets_minimum_versions` | Alias `version_ok` |
| `installable` | `ubuntu`/`debian` + `apt-get` |

## Funktionen und Klassen

### `_run(cmd, *, check=False) -> CompletedProcess[str]`

**Beschreibung:** Wrapper um `subprocess.run` mit captured stdout/stderr.

---

### `_parse_version(text: str) -> tuple[int, int, int] | None`

**Beschreibung:** Erstes `major.minor.patch` per Regex.

---

### `is_wsl() -> bool`

**Beschreibung:** `WSL_DISTRO_NAME` oder „microsoft“ in `/proc/version`.

---

### `read_os_release() -> dict[str, str]`

**Beschreibung:** Parst `/etc/os-release`.

---

### `docker_group_in_session() -> bool`

**Beschreibung:** `docker`-GID in `os.getgroups()`.

---

### `user_in_docker_group(username=None) -> bool`

**Beschreibung:** `id -nG` enthält `docker`.

---

### `_sudo_docker_info_ok() -> bool`

**Beschreibung:** `docker info` als root oder via `sudo`.

---

### `systemd_is_running() -> bool`

**Beschreibung:** `systemctl is-system-running` Exit 0.

---

### `wsl_systemd_enabled() / wsl_needs_restart_for_systemd()`

**Beschreibung:** Prüft `systemd=true` in `wsl.conf` vs. laufendes systemd.

---

### `_version_at_least(found, minimum) -> bool`

**Beschreibung:** Tuple-Vergleich.

---

### `_docker_packages_current() -> bool`

**Beschreibung:** `dpkg-query` für `docker-ce` und `docker-compose-plugin`.

---

### `_docker_engine_version() -> tuple | None`

**Beschreibung:** Server-, Client- oder CLI-Version.

---

### `check_docker() -> DockerStatus`

**Beschreibung:** Vollständige Erhebung; füllt `notes` bei Permission/WSL/Version/Gruppe.

**Ablauf / lokale Variablen:** `combined` — stdout+stderr von `docker info` für „permission denied“.

---

### `assert_docker_ready(status, *, context="Setup") -> None`

**Beschreibung:** `SystemExit(1)` wenn nicht ready; Ausnahme wenn Daemon ok aber Session-Gruppe fehlt (newgrp-Hinweis).

---

### `print_docker_status(status) -> None`

**Beschreibung:** Menschenlesbare Checkliste auf stdout.

---

### `_sudo_cmd(args) -> list[str]`

**Beschreibung:** Prefix `sudo` wenn nicht root.

---

### `run_with_docker_session(cmd, *, cwd, env) -> CompletedProcess`

**Beschreibung:** Führt Docker-Befehl aus; bei Gruppe gesetzt aber Session alt: `sg docker -c "…"`.

---

### `_sudo_run(args) -> None`

**Beschreibung:** `DEBIAN_FRONTEND=noninteractive`, `check=True`.

---

### `install_docker_engine(*, force=False) -> None`

**Beschreibung:** APT-Repo von download.docker.com, Pakete `docker-ce`, `docker-compose-plugin`, `usermod -aG docker`, optional `systemctl enable --now docker`.

**Ablauf / lokale Variablen:** `keyring`, `list_file`, `tmp_gpg`, `tmp_list` — Staging unter `/tmp`.

---

### `ensure_docker(*, interactive, auto_install, skip_install) -> DockerStatus`

**Beschreibung:** Wenn `ready` → kurze Meldung; sonst ggf. WSL-Prompt und `install_docker_engine` nach `_prompt_install`.

---

### `_prompt_install() -> bool`

**Beschreibung:** Interaktive j/n-Schleife.

---

### `main() -> None`

**Beschreibung:** `--install` → install + status; sonst `ensure_docker` mit `skip_install` bei `--check` / `--check-bootstrap`; Exit 1 wenn Checks fehlschlagen.

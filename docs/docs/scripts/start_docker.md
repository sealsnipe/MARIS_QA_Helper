# `scripts/start_docker.py`

**Quellpfad:** `scripts/start_docker.py`

## Zweck und logischer Aufbau

**Best-effort-Start** des Docker-Daemons nach Installation (Ubuntu/WSL): `systemctl`/`service`, optional Hintergrund-`dockerd`, Warte-Schleifen und spezielle Exit-Codes wenn WSL nach Aktivierung von systemd neu gestartet werden muss.

Wird typischerweise aus `install.sh` aufgerufen, nicht für täglichen App-Start.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `scripts/docker_preflight.py` — `check_docker`, `is_wsl`, `systemd_is_running`, `wsl_needs_restart_for_systemd`
- **Wird genutzt von:** Install-Flow
- **CLI:** direkt `python3 scripts/start_docker.py`; Exit `2` = WSL-Neustart nötig (`NEEDS_WSL_RESTART`)

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `NEEDS_WSL_RESTART` | `int` | Exit-Code `2` |
| (importiert) | — | Preflight-Helfer aus gleichem `scripts/`-Ordner |

## Funktionen und Klassen

### `_log(msg: str) -> None`

**Beschreibung:** Print mit `flush=True`.

---

### `_run(cmd: list[str]) -> int`

**Beschreibung:** `subprocess.run` ohne Check, gibt Returncode zurück.

---

### `_daemon_reachable() -> bool`

**Beschreibung:** `check_docker().daemon_ok` oder `daemon_ok_sudo`.

---

### `_try_start_daemon() -> None`

**Beschreibung:** Wenn `systemctl` und systemd läuft: `enable` + `start docker` (root oder sudo); sonst `service docker start`.

---

### `_try_dockerd_background() -> None`

**Beschreibung:** Startet `dockerd` per `Popen`, Logs nach `/var/log/dockerd-maris.log`.

---

### `_wait_for_daemon(*, seconds: int, label: str) -> bool`

**Beschreibung:** Pollt alle 2 s bis Deadline, ob Daemon erreichbar.

---

### `_print_wsl_restart_hint() -> None`

**Beschreibung:** Anleitung `wsl --shutdown`, `./install.sh --continue`, Docker Desktop-Alternative.

---

### `main() -> None`

**Beschreibung:** Wenn Daemon schon ok → return; bei `wsl_needs_restart_for_systemd` → Hint + Exit 2; sonst starten und warten (30/90 s je nach WSL/systemd); ggf. `dockerd`-Fallback; bei Fehler Exit 1 mit plattformspezifischen Hinweisen.

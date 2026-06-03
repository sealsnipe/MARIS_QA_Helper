# `install.sh`

**Quellpfad:** `install.sh`

## Zweck

Bootstrap auf **frischem Ubuntu/WSL**: Systempakete, Docker Engine und Compose installieren, Daemon starten und anschließend den Setup-Wizard (`scripts/setup.py`) ausführen. Unter WSL kann `systemd=true` in `/etc/wsl.conf` gesetzt werden — danach ist ein WSL-Neustart nötig (`./install.sh --continue`).

## Ablauf (kurz)

1. Repo-Root ermitteln; CLI-Flags `--install-only`, `--continue` auswerten.
2. Plattform prüfen (`/etc/os-release`); unter WSL ggf. `/etc/wsl.conf` mit `[boot] systemd=true` schreiben.
3. **Mit `--continue`:** `python3 scripts/start_docker.py` (Exit `2` = WSL-Neustart nötig), dann `scripts/docker_preflight.py --check-bootstrap`.
4. **Ohne `--continue`:** apt `git`, `python3`, `python3-pip`, `curl`, `ca-certificates`; optional `pip install --user httpx oauth-codex`; `scripts/docker_preflight.py --install`; `start_docker.py`; Bootstrap-Check; bei WSL/systemd-Hinweis ggf. früh beenden mit Hinweis auf `--continue`.
5. Bei `--install-only`: Setup überspringen, Hinweise auf `./install.sh --continue` und `./setup.sh`.
6. Sonst: ggf. `sg docker` wenn Gruppe `docker` in Session fehlt; `exec python3 scripts/setup.py --skip-docker-check` mit durchgereichten Args.

## Konfiguration / Parameter

| Flag / Argument | Wirkung |
|---|---|
| `--install-only` | Nur Pakete + Docker, kein `setup.py` |
| `--continue` | Nach WSL-Neustart: Docker starten/prüfen, dann Setup |
| `--non-interactive` | Wird an `setup.py` durchgereicht (Erkennung per `grep` in `"$@"`) |
| Weitere Args | An `scripts/setup.py` durchgereicht |

| Aufgerufene Skripte | Rolle |
|---|---|
| `scripts/start_docker.py` | Docker-Daemon starten; Rückgabecode `2` = WSL-Neustart |
| `scripts/docker_preflight.py` | `--install`, `--check-bootstrap` |
| `scripts/setup.py` | Credentials, `.env`, optional Compose (`--skip-docker-check`) |

| Hilfsfunktion | Kurzbeschreibung |
|---|---|
| `run_as_root` | `sudo` oder direkt als root |
| `finish_install_only` | Log-Hinweise für nächste Schritte |

## Siehe auch

- [`docs/docs/setup.md`](./setup.md) — Setup wenn Docker bereits läuft
- [`docs/docs/scripts/setup.md`](./scripts/setup.md) — Python-Setup-Wizard (noch anzulegen)
- [`docs/docs/scripts/docker_preflight.md`](./scripts/docker_preflight.md) — Docker-Installation (noch anzulegen)
- [`docs/11_setup_and_operations.md`](../11_setup_and_operations.md)

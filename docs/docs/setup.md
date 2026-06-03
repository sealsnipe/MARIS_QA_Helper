# `setup.sh`

**Quellpfad:** `setup.sh`

## Zweck

Einzeiler-Einstieg für das **Erst-Setup** der Anwendung (Env, Credentials, optional Docker Compose), wenn Systempakete und Docker bereits vorhanden sind. Installiert keine OS-Pakete — dafür ist `install.sh` zuständig.

## Ablauf (kurz)

1. `set -euo pipefail`, Wechsel ins Verzeichnis des Skripts (`cd "$(dirname "$0")"`).
2. `exec python3 scripts/setup.py "$@"` — alle CLI-Argumente gehen an den Python-Wizard.

## Konfiguration / Parameter

| Aspekt | Detail |
|---|---|
| CLI-Args | Vollständig an `scripts/setup.py` durchgereicht (z. B. `--non-interactive`, `--openai-key`, Profil-/Auth-Flags — siehe `setup.py`) |
| Voraussetzung | Docker-Daemon läuft, wenn Compose-Start im Wizard gewählt wird (im Gegensatz zu `install.sh` kein `--skip-docker-check` hier) |

## Siehe auch

- [`docs/docs/install.md`](./install.md) — vollständiger Bootstrap inkl. Docker-Installation
- [`docs/docs/scripts/setup.md`](./scripts/setup.md) — `scripts/setup.py` (noch anzulegen)
- [`docs/docs/.env.example.md`](./.env.example.md) — Env-Vorlage
- [`docs/11_setup_and_operations.md`](../11_setup_and_operations.md)

# `scripts/restart.sh`

**Quellpfad:** `scripts/restart.sh`

## Zweck

Startet den MARIS Q/A Helper Docker-Stack neu: vollständiger Stop und anschließender Start. `./data` und `.env` bleiben unverändert.

## Ablauf (kurz)

1. Repo-Root ermitteln (`dirname` → `..`).
2. `./scripts/stop.sh` ausführen.
3. `./scripts/start.sh` ausführen.

## Konfiguration / Parameter

Keine CLI-Argumente. Compose-Profil und OAuth-Mount kommen indirekt über [`compose_env.sh`](./compose_env.md) in `start.sh` / `stop.sh`.

## Siehe auch

- [`start.md`](./start.md)
- [`stop.md`](./stop.md)
- [`compose_env.md`](./compose_env.md) (B3)

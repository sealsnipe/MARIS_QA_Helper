# `scripts/stop.sh`

**Quellpfad:** `scripts/stop.sh`

## Zweck

Stoppt den Docker-Compose-Stack. Persistente Daten unter `./data` und die lokale `.env` bleiben erhalten.

## Ablauf (kurz)

1. Repo-Root, `source scripts/compose_env.sh`, `compose_env`.
2. `compose_run down` mit der aus `.env` abgeleiteten Compose-Dateiliste.
3. Hinweise auf `start.sh` und `update.sh`.

## Konfiguration / Parameter

Keine eigenen CLI-Args; Compose-Variante über [`compose_env.sh`](./compose_env.md) und `.env`.

## Siehe auch

- [`start.md`](./start.md)
- [`update.md`](./update.md)
- [`compose_env.md`](./compose_env.md)

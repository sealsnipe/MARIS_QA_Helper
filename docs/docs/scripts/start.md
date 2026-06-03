# `scripts/start.sh`

**Quellpfad:** `scripts/start.sh`

## Zweck

Startet den produktiven bzw. konfigurierten Docker-Compose-Stack (API + Qdrant) gemäß `.env` und prüft danach den Health-Endpoint.

## Ablauf (kurz)

1. Repo-Root, `source scripts/compose_env.sh`, `compose_env` (liest `.env`, setzt `COMPOSE`-Dateiliste).
2. `compose_run up -d --build`.
3. Kurz warten, `curl` auf `http://127.0.0.1:${APP_PORT:-8088}/api/health`.
4. URL und Log-Hinweis ausgeben.

## Konfiguration / Parameter

| Quelle | Bedeutung |
|---|---|
| `.env` | `DEPLOY_PROFILE`, `LLM_AUTH_MODE`, `APP_PORT`, OAuth-Pfade — via `compose_env.sh` |
| `APP_PORT` | Default `8088` für Health-URL |

## Siehe auch

- [`stop.md`](./stop.md)
- [`update.md`](./update.md)
- [`compose_env.md`](./compose_env.md)
- [`docker-compose.md`](../docker-compose.md)

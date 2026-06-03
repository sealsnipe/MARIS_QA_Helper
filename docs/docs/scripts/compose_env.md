# `scripts/compose_env.sh`

**Quellpfad:** `scripts/compose_env.sh`

## Zweck

Gemeinsame **Docker-Compose-Dateiauswahl** aus `./.env` und Umgebungsvariablen. Wird von `scripts/start.sh`, `scripts/stop.sh` und `scripts/update.sh` per `source` geladen; setzt das Bash-Array `COMPOSE` und stellt `compose_run` für korrekte `docker`-Gruppen-Rechte bereit.

## Ablauf (kurz)

1. Aufrufer: `source compose_env.sh`, dann `compose_env` — `COMPOSE=(docker compose -f docker-compose.yml)`.
2. `DEPLOY_PROFILE` und `LLM_AUTH_MODE` aus Env; falls leer, aus `.env` per `grep` (letzte Zeile pro Key).
3. Fehlt `DEPLOY_PROFILE`: aus `SESSION_COOKIE_SECURE` in `.env` ableiten (`true` → `prod`, sonst `dev`).
4. `profile=prod` → `-f docker-compose.prod.yml`; sonst bei `llm=chatgpt_oauth` → `-f docker-compose.oauth.yml` und ggf. `OAUTH_AUTH_HOST_PATH` aus `CODEX_OAUTH_AUTH_PATH` oder Default `$HOME/.oauth_codex/auth.json`.
5. `compose_run "$@"` führt `${COMPOSE[@]}` aus; bei fehlender `docker`-Gruppe in der Session aber Mitgliedschaft in `docker`: `sg docker -c "…"`.

## Konfiguration / Parameter

| Funktion | Beschreibung |
|---|---|
| `compose_env()` | Baut `COMPOSE`-Array; liest `.env` im aktuellen `PWD` |
| `compose_run()` | Wrapper um `docker compose` mit `sg docker` falls nötig |
| `_docker_group_in_session()` | Prüft, ob GID der Gruppe `docker` in `id -G` vorkommt |

| Variable (Env / `.env`) | Wirkung auf `COMPOSE` |
|---|---|
| `DEPLOY_PROFILE` | `prod` → `docker-compose.prod.yml` |
| `LLM_AUTH_MODE` | `chatgpt_oauth` (wenn nicht prod) → `docker-compose.oauth.yml` |
| `SESSION_COOKIE_SECURE` | Fallback-Profil: `true` → `prod`, sonst `dev` |
| `CODEX_OAUTH_AUTH_PATH` | Host-Pfad für OAuth-Mount; `~` → `$HOME` |
| `OAUTH_AUTH_HOST_PATH` | Exportiert, wenn nicht gesetzt und OAuth-Overlay aktiv |

| Basis-Compose | Immer |
|---|---|
| `-f docker-compose.yml` | Erste Datei in `COMPOSE` |

## Siehe auch

- [`docs/docs/docker-compose.md`](../docker-compose.md) — Basis
- [`docs/docs/docker-compose.prod.md`](../docker-compose.prod.md) — Prod-Overlay
- [`docs/docs/docker-compose.oauth.md`](../docker-compose.oauth.md) — OAuth-Overlay
- [`docs/docs/scripts/start.md`](./start.md) — Nutzer von `compose_env` (noch anzulegen)
- [`docs/docs/scripts/stop.md`](./stop.md) — Nutzer von `compose_env` (noch anzulegen)
- [`docs/docs/scripts/update.md`](./update.md) — Nutzer von `compose_env` (noch anzulegen)

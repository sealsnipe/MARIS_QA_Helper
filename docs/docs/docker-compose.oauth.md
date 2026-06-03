# `docker-compose.oauth.yml`

**Quellpfad:** `docker-compose.oauth.yml`

## Zweck

Compose-Overlay, um **ChatGPT-OAuth-Auth** vom Host read-only in den API-Container zu mounten und `LLM_AUTH_MODE` auf `chatgpt_oauth` zu setzen. Wird zusammen mit `docker-compose.yml` gestartet; Host-Pfad muss über `OAUTH_AUTH_HOST_PATH` gesetzt sein.

## Ablauf (kurz)

1. `OAUTH_AUTH_HOST_PATH` auf den Pfad der Host-Datei `auth.json` setzen (Pflicht — Compose bricht sonst mit Fehlermeldung ab).
2. Start: `docker compose -f docker-compose.yml -f docker-compose.oauth.yml up -d` (siehe Kommentar in der Quelldatei).
3. `scripts/compose_env.sh` wählt dieses Overlay automatisch, wenn `LLM_AUTH_MODE=chatgpt_oauth` (aus Env oder `.env`) und Profil nicht `prod`.

## Konfiguration / Parameter

| Variable / Platzhalter | Verwendung |
|---|---|
| `OAUTH_AUTH_HOST_PATH` | Host-Pfad zur Auth-JSON; Pflicht beim Compose-Start (`:?`-Expansion in Volume-Quelle) |
| Container-Ziel | `/root/.oauth_codex/auth.json` (read-only) |

| Service | `environment` | Wert |
|---|---|---|
| `api` | `LLM_AUTH_MODE` | `chatgpt_oauth` |
| `api` | `CODEX_OAUTH_AUTH_PATH` | `/root/.oauth_codex/auth.json` |

| Service | `volumes` (Auszug) | Mapping |
|---|---|---|
| `api` | Host → Container | `${OAUTH_AUTH_HOST_PATH}:.../auth.json:ro` |

## Siehe auch

- [`docs/docs/docker-compose.md`](./docker-compose.md) — Basis-API-Service
- [`docs/docs/scripts/compose_env.md`](./scripts/compose_env.md) — Overlay-Auswahl und `OAUTH_AUTH_HOST_PATH`-Default
- [`docs/docs/.env.example.md`](./.env.example.md) — `LLM_AUTH_MODE`, `CODEX_OAUTH_AUTH_PATH`

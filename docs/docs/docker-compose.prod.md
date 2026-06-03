# `docker-compose.prod.yml`

**Quellpfad:** `docker-compose.prod.yml`

## Zweck

**Produktions-Overlay** für Docker Compose: TLS-taugliche Session-Cookies, API-Key-Chat im Container (kein Browser-OAuth) und festes Chat-Modell. Wird mit `docker-compose.yml` kombiniert; `scripts/compose_env.sh` hängt diese Datei an, wenn `DEPLOY_PROFILE=prod` (oder abgeleitet aus `.env`).

## Ablauf (kurz)

1. Start: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build` (siehe Kommentar in der Quelldatei).
2. Überschreibt nur `services.api.environment` — Build, Ports und Volumes kommen aus der Basisdatei.
3. Betrieb typischerweise hinter Reverse-Proxy mit HTTPS; `SESSION_COOKIE_SECURE=true` setzt Secure-Cookies voraus.

## Konfiguration / Parameter

| Service | Variable | Wert | Beschreibung |
|---|---|---|---|
| `api` | `SESSION_COOKIE_SECURE` | `"true"` | Session-Cookie nur über HTTPS |
| `api` | `LLM_AUTH_MODE` | `api_key` | OpenAI Platform API-Key (kein OAuth im Container) |
| `api` | `CHAT_MODEL` | `gpt-4.1-mini` | Standard-Chatmodell in Prod |

Keine zusätzlichen Services oder Volumes in dieser Datei.

## Siehe auch

- [`docs/docs/docker-compose.md`](./docker-compose.md) — Basis-Stack
- [`docs/docs/scripts/compose_env.md`](./scripts/compose_env.md) — `DEPLOY_PROFILE=prod` → dieses Overlay
- [`docs/docs/.env.example.md`](./.env.example.md) — `DEPLOY_PROFILE`, `SESSION_COOKIE_SECURE`
- [`docs/11_setup_and_operations.md`](../11_setup_and_operations.md)

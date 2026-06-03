# `docker-compose.yml`

**Quellpfad:** `docker-compose.yml`

## Zweck

Basis-Compose-Definition für den MARIS Q/A Helper-Stack: FastAPI-**API** (Build aus `backend/Dockerfile`) und **Qdrant** als Vektordatenbank. Liest `.env`, persistiert App-Daten unter `./data` und Qdrant in einem Named Volume.

## Ablauf (kurz)

1. `docker compose up -d --build` startet beide Services (Standard-CLI ohne Overlay-Dateien).
2. `api` wartet auf `qdrant` (`depends_on`), Port `8088:8088`, Neustart `unless-stopped`.
3. Erweiterungen: Overlays `docker-compose.prod.yml`, `docker-compose.oauth.yml`, `docker-compose.dev-local.yml` — Auswahl auch über `scripts/compose_env.sh`.

## Konfiguration / Parameter

### Service `api`

| Schlüssel | Wert | Beschreibung |
|---|---|---|
| `build.context` | `.` | Projektroot |
| `build.dockerfile` | `backend/Dockerfile` | API-Image |
| `ports` | `8088:8088` | HTTP API und Web-UI |
| `env_file` | `.env` | Laufzeit-Konfiguration |
| `volumes` | `./data:/app/data` | SQLite und Uploads |
| `depends_on` | `qdrant` | Startreihenfolge |
| `restart` | `unless-stopped` | Automatischer Neustart |

### Service `qdrant`

| Schlüssel | Wert | Beschreibung |
|---|---|---|
| `image` | `qdrant/qdrant:latest` | Vektor-DB |
| `ports` | `6333:6333` | HTTP-API |
| `volumes` | `qdrant_storage:/qdrant/storage` | Persistente Indizes |
| `restart` | `unless-stopped` | Automatischer Neustart |

### Volumes

| Name | Zweck |
|---|---|
| `qdrant_storage` | Persistenter Qdrant-Speicher (Compose-managed) |

## Siehe auch

- [`docs/docs/backend/Dockerfile.md`](./backend/Dockerfile.md) — API-Image
- [`docs/docs/docker-compose.prod.md`](./docker-compose.prod.md) — Produktions-Overlay
- [`docs/docs/docker-compose.oauth.md`](./docker-compose.oauth.md) — OAuth-Mount-Overlay
- [`docs/docs/docker-compose.dev-local.md`](./docker-compose.dev-local.md) — Dev-Ports und `.env.dev`
- [`docs/docs/scripts/compose_env.md`](./scripts/compose_env.md) — Compose-Dateiauswahl aus `.env`

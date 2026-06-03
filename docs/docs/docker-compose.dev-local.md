# `docker-compose.dev-local.yml`

**Quellpfad:** `docker-compose.dev-local.yml`

## Zweck

Compose-Overlay für eine **lokale Dev-Kopie** des Stacks auf alternativen Ports (Kommentar: Windows-Browser `http://localhost:8090`). Ergänzt `docker-compose.yml` um abweichende Port-Mappings, `.env.dev` und persistente Daten unter `./data-dev`.

## Ablauf (kurz)

1. Basis-Stack starten: `docker compose -f docker-compose.yml -f docker-compose.dev-local.yml up -d --build` (siehe Kommentar in der Quelldatei).
2. Service `api`: Port `8090:8088`, `env_file` `.env.dev`, Volume `./data-dev:/app/data`.
3. Service `qdrant`: Port `6334:6333`, Named Volume `qdrant_dev_storage` statt `qdrant_storage`.

## Konfiguration / Parameter

| Service | Einstellung | Wert | Beschreibung |
|---|---|---|---|
| `api` | `ports` | `8090:8088` | Host 8090 → Container 8088 |
| `api` | `env_file` | `.env.dev` | Dev-Env statt `.env` |
| `api` | `volumes` | `./data-dev:/app/data` | SQLite/Uploads unter `data-dev/` |
| `qdrant` | `ports` | `6334:6333` | Host 6334 → Qdrant HTTP 6333 |
| `qdrant` | `volumes` | `qdrant_dev_storage:/qdrant/storage` | Separates Dev-Volume |

| Volume | Zweck |
|---|---|
| `qdrant_dev_storage` | Qdrant-Persistenz für Dev-Overlay (getrennt von `qdrant_storage` in der Basisdatei) |

## Siehe auch

- [`docs/docs/docker-compose.md`](./docker-compose.md) — Basis-Services `api` und `qdrant`
- [`docs/docs/.env.dev.example.md`](./.env.dev.example.md) — Vorlage für `.env.dev`
- [`docs/docs/scripts/dev_local.md`](./scripts/dev_local.md) — natives Dev ohne Docker (Port 8090, noch anzulegen)

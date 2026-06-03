# 01 — Laufzeit-Topologie

**Stand:** 2026-06-03

---

## Überblick

```text
                    ┌─────────────────────────────────────┐
                    │           Browser (User)             │
                    └──────────────────┬──────────────────┘
                                       │ HTTP
         ┌─────────────────────────────┼─────────────────────────────┐
         │                             ▼                             │
         │  FastAPI (uvicorn)  —  Session + Jinja + Static           │
         │       │                    │                    │          │
         │       ▼                    ▼                    ▼          │
         │   SQLite              Qdrant              OpenAI / Codex   │
         │  (Metadaten)      (Vektoren/kb_*)        (Embed + Chat)   │
         │       │                                                    │
         │       └── ./data/uploads/{customer_id}/…  (Dateien)        │
         └────────────────────────────────────────────────────────────┘
```

---

## Betriebsmodi

| Modus | Port API | Qdrant | Config | Skript |
|---|---|---|---|---|
| **Docker Standard** | 8088 | `:6333` (Container) | `.env` | `./scripts/start.sh`, `docker-compose.yml` |
| **Docker Prod** | 8088 | Container | `.env` + Overlay | `docker-compose.prod.yml` (`SESSION_COOKIE_SECURE=true`) |
| **Docker OAuth** | 8088 | Container | OAuth-Volume | `docker-compose.oauth.yml` |
| **Dev lokal (WSL)** | **8090** | **:6334** (Binary) | `.env.dev` | `./scripts/dev_local.sh` |
| **Dev lokal Compose** | 8090 | Container | `.env.dev` | `docker-compose.dev-local.yml` |

Details Spiegel: [`docs/docs/scripts/dev_local.md`](../docs/scripts/dev_local.md), [`docs/docs/docker-compose.md`](../docs/docker-compose.md)

---

## Docker Compose (Standard)

| Service | Rolle | Volume |
|---|---|---|
| `api` | FastAPI-App, baut aus `backend/Dockerfile` | `./data` → SQLite + Uploads |
| `qdrant` | Vektor-DB | `qdrant_storage` |

Health: `GET /api/health` → `{"ok":true}`

---

## Dev lokal ohne Docker Desktop

`scripts/dev_local.sh`:

1. Lädt/startet Qdrant-Binary nach `.tools/qdrant` (Port **6334**)
2. Daten in `./data-dev/` (SQLite, Qdrant-Storage, PIDs, Logs)
3. Uvicorn auf **8090** mit `.env.dev`

Windows/WSL-Zugriff: `http://localhost:8090`

---

## Externe Abhängigkeiten

| System | Konfiguration | Zweck |
|---|---|---|
| OpenAI API | `OPENAI_API_KEY`, `OPENAI_BASE_URL` | Embeddings (immer) |
| OpenAI oder Codex OAuth | `LLM_AUTH_MODE`, `CHAT_MODEL` | Chat-Antworten |
| Qdrant | `QDRANT_URL`, `COLLECTION_PREFIX` | Vektor-Suche pro Mandant |

---

## Betroffene Spiegel-Dateien

`backend/app/main.md`, `backend/app/config.md`, `docker-compose*.md`, `scripts/dev_local.md`, `scripts/start.md`, `qdrant.md`, `.env.example.md`

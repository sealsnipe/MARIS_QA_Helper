# 09 — Modul-Abhängigkeiten

**Stand:** 2026-06-05 (nach Review: alle Post-MVP-Module ergänzt)

---

## Schichten

```text
┌────────────────────────────────────────────────────────────────────────────┐
│  routes.py + integration_routes.py + templates + static/app.js             │  HTTP / UI
├────────────────────────────────────────────────────────────────────────────┤
│  agent  │  chats  │  ingestion/upload  │  knowledge_center                │  Anwendung
│  users_admin │ customers │ system_prompts │ document_merge │ duplicates   │
│  roles_admin │ secrets_admin                                             │
├────────────────────────────────────────────────────────────────────────────┤
│  retrieval  │  chunking  │  prompts  │  document_fingerprints / assets    │  RAG-Kern + Dedup
├────────────────────────────────────────────────────────────────────────────┤
│  llm  │  embeddings  │  qdrant_store  │  loaders ( + vision/ocr/image )    │  Infrastruktur
│  content_hash  │  oauth_device_flow (optional)                           │
├────────────────────────────────────────────────────────────────────────────┤
│  auth  │  tenant  │  models  │  db  │  config  │  integration_auth        │  Plattform
└────────────────────────────────────────────────────────────────────────────┘
```
Hinweis: `integration_routes` + `integration_auth` sind separat gemountet (kein Session-Tenant); `main.py` nur Mount + Exceptions + Lifespan.


---

## Kern-Abhängigkeiten (Auszug)

| Modul | Ruft auf | Wird gerufen von |
|---|---|---|
| `routes` | fast alle App-Module (inkl. upload/ingest/agent/customers/...) | `main` |
| `integration_routes` | `agent`, `chats`, `knowledge_center`, `customers` | `main` (separater Mount), Integration-Clients |
| `agent` | `llm`, `retrieval`, `system_prompts`, `prompts` | `routes`, `integration_routes` |
| `retrieval` | `embeddings`, `qdrant_store`, `customers` | `agent`, `chats` (filter) |
| `ingestion` | `chunking`, `embeddings`, `qdrant_store`, `document_fingerprints?` | `routes`, `upload`, `knowledge_center`, `document_merge` |
| `upload` | `loaders`, `ingestion`, `duplicates`, `document_fingerprints`, `document_assets`, vision | `routes` |
| `knowledge_center` | `customers`, `ingestion`, `models` | `integration_routes`, `routes` (Tools) |
| `document_merge` | `ingestion` (update), `llm` (optional), embeddings | `routes` (Admin KB) |
| `duplicates` / `document_fingerprints` / `content_hash` | `models`, qdrant (fp), content_hash | `upload`, `document_merge` (Checks) |
| `customers` | `models`, `qdrant_store` (rename/copy), roles_admin (auto) | `tenant`, `routes`, `users_admin`, `retrieval`, `knowledge_center`, `integration_routes` |
| `roles_admin` / `secrets_admin` / `users_admin` | `models`, `customers` (teilw.) | `routes` (Admin), `customers` (create auto) |
| `tenant` | `auth`, `customers` | `routes` |
| `oauth_device_flow` | httpx, FS (~/.codex/auth.json) | `secrets_admin` |
| `main` | `routes`, `integration_routes`, `db`, Exception-Handler (alle *AdminError etc.) | uvicorn entry |

Vollständige Traces: Spiegel-Dateien unter `docs/docs/backend/app/`.  
Aktueller Stand der Spiegel: `docs/docs/INDEX.md` (nach Review 2026-06 alle 25 fehlenden nachgezogen).

---

## Externe Pakete

| Paket | Nutzung |
|---|---|
| FastAPI, Starlette | HTTP, Sessions, Static |
| SQLAlchemy | ORM |
| qdrant-client | Vektorspeicher |
| openai | Embeddings + optional Chat |
| oauth_codex | Optional Codex OAuth LLM |
| pypdf, python-docx | Loader |
| pillow | Vision images |
| httpx | OAuth Device Flow (optional) |

---

## Entry Points

| Entry | Datei |
|---|---|
| Production API | `app.main:app` |
| Tests | `pytest` → `conftest.py` |
| Seed/Setup | `scripts/*.py` (inkl. seed_knowledge_center_demo.py) |

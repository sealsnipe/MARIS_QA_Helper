# 09 — Modul-Abhängigkeiten

**Stand:** 2026-06-03

---

## Schichten

```text
┌─────────────────────────────────────────────────────────┐
│  routes.py  +  templates  +  static/app.js              │  HTTP / UI
├─────────────────────────────────────────────────────────┤
│  agent  │  chats  │  ingestion/upload  │  users_admin   │  Anwendung
│         │         │  customers  │  system_prompts       │
├─────────────────────────────────────────────────────────┤
│  retrieval  │  chunking  │  prompts                     │  RAG-Kern
├─────────────────────────────────────────────────────────┤
│  llm  │  embeddings  │  qdrant_store  │  loaders         │  Infrastruktur
├─────────────────────────────────────────────────────────┤
│  auth  │  tenant  │  models  │  db  │  config            │  Plattform
└─────────────────────────────────────────────────────────┘
```

---

## Kern-Abhängigkeiten (Auszug)

| Modul | Ruft auf | Wird gerufen von |
|---|---|---|
| `routes` | fast alle App-Module | `main` |
| `agent` | `llm`, `retrieval`, `system_prompts`, `prompts` | `routes` |
| `retrieval` | `embeddings`, `qdrant_store`, `customers` | `agent`, `chats` (filter) |
| `ingestion` | `chunking`, `embeddings`, `qdrant_store` | `routes`, `upload` |
| `upload` | `loaders`, `ingestion` | `routes` |
| `customers` | `models`, `qdrant_store` (rename) | `tenant`, `routes`, `users_admin`, `retrieval` |
| `tenant` | `auth`, `customers` | `routes` |
| `main` | `routes`, `db`, Exception-Handler | uvicorn entry |

Vollständige Traces: Spiegel-Dateien unter `docs/docs/backend/app/`.

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

---

## Entry Points

| Entry | Datei |
|---|---|
| Production API | `app.main:app` |
| Tests | `pytest` → `conftest.py` |
| Seed/Setup | `scripts/*.py` |

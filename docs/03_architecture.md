# 03 — Architektur

**Stand:** 2026-06-05 · **Status:** verbindlich für MVP + Post-MVP (Review-Sync)

> Querschnitt: [`system/09_module_dependency_map.md`](../system/09_module_dependency_map.md)

---

## 1. Überblick

SUP_QA_Helper ist eine FastAPI-Anwendung mit server-gerenderten Seiten, Login-Gate,
**mandantengetrenntem** agentengestütztem RAG-Kern und zwei Datenspeichern (SQLite für
Metadaten/Nutzer/Kunden, Qdrant für Vektoren — **eine Collection pro Kunde**). Wissen kommt per
**Text und Datei-Upload** rein. Modell-Aufrufe gehen an OpenAI.

```text
                         ┌──────────────────────────────────────────────────┐
   Browser               │                    FastAPI App                    │
 ┌──────────┐  HTTP      │  ┌────────────────────────────────────────────┐   │
 │ Login    │──────────▶ │  │ Auth (SessionMiddleware + Argon2id)         │   │
 │ Kundenwahl│           │  │ Tenant (get_current_customer: user∈customer)│   │
 │ Hauptseite│           │  └────────────────────────────────────────────┘   │
 │  - KB     │           │     │ schützt + scoped jede Inhalts-/Chat-Route    │
 │   Text    │           │     ▼                                              │
 │   Datei   │           │  ┌── Routes (HTML + JSON API) ──────────────┐      │
 │  - Chat   │           │  │ / /login /api/customers /api/session/... │      │
 └──────────┘            │  │ /api/documents(+text) /api/chat /health  │      │
                         │  └───────────────┬──────────────────────────┘      │
                         │      ┌───────────┼─────────────┬───────────┐       │
                         │      ▼           ▼             ▼           ▼       │
                         │ ┌─────────┐ ┌────────┐  ┌──────────┐ ┌────────┐   │
                         │ │ Loaders │ │Ingestion│  │  Agent   │ │ Auth/  │   │
                         │ │txt/md/  │▶│ingest_  │  │  loop    │ │ Tenant │   │
                         │ │pdf/docx │ │text()   │  │ search_kb│ │        │   │
                         │ └─────────┘ └───┬────┘  └────┬─────┘ └───┬────┘   │
                         └──────────────────┼────────────┼───────────┼─────────┘
                                            ▼            ▼ (kb_{cid}) ▼
                                     ┌──────────┐ ┌─────────┐  ┌──────────────┐
                                     │  Qdrant  │ │ OpenAI  │  │   SQLite     │
                                     │ kb_acme  │ │ embed + │  │ users        │
                                     │ kb_globex│ │ chat    │  │ customers    │
                                     └──────────┘ └─────────┘  │ user_customers│
                                                               │ documents    │
                                                               │ chunks       │
                                                               └──────────────┘
   Dateispeicher: ./data/uploads/{customer_id}/{document_id}/{safe_filename}
```

## 2. Komponenten & Verantwortlichkeiten

| Komponente | Datei (vgl. §7) | Verantwortung |
|---|---|---|
| App-Bootstrap | `app/main.py` | FastAPI-Init, Middleware, Startup (DB), Router-Mount |
| Konfiguration | `app/config.py` | `.env` laden, typisiert, Fail-fast bei fehlendem Key/Secret |
| Auth | `app/auth.py` | Login/Logout, Argon2id, `get_current_user` |
| **Tenant** | `app/tenant.py` | `get_current_customer` (Session + `user∈customer`-Check → 403) |
| **Kunden** | `app/customers.py` | `customers`-Registry-Zugriff, erlaubte Kunden je Nutzer |
| Routen | `app/routes.py` | HTML- + JSON-Endpoints, Validierung, Fehlerformat |
| **Loaders** | `app/loaders/` | Text aus `.txt/.md` direkt, `.pdf` (pypdf), `.docx` (python-docx) |
| Ingestion | `app/ingestion.py` | `ingest_text(customer_id, ...)`: chunk → embed → upsert → Metadaten |
| Chunking | `app/chunking.py` | Normalisierung, Split mit Overlap |
| Embeddings | `app/embeddings.py` | OpenAI-Embeddings, Batching, mockbar |
| LLM | `app/llm.py` | OpenAI-Chat-Client mit Tool-Calling |
| Agent | `app/agent.py` | Tool-Loop **an aktiven Kunden gebunden**, Citation-Aggregation |
| **Chats** | `app/chats.py` | Sessions/Messages pro User+Mandant |
| **Users Admin** | `app/users_admin.py` | Benutzer-CRUD, Mandantenzuordnung |
| **System Prompts** | `app/system_prompts.py` | Global + pro Mandant, effektiver Prompt |
| Prompts | `app/prompts.py` | System-Prompt-Konstanten, Tool-Schema |
| Vektor-Store | `app/qdrant_store.py` | `collection_name(cid)`, `ensure_collection`, `upsert/search/delete` (parametrisiert) |
| Persistenz | `app/db.py`, `app/models.py` | SQLAlchemy, `create_all`, ORM-Modelle |

## 3. Tech-Stack

| Bereich | Wahl | Hinweis |
|---|---|---|
| Sprache | Python 3.12 | |
| Web | FastAPI + Uvicorn | server-gerendert, 1 Worker (SQLite) |
| Templates | Jinja2 | + minimal Vanilla-JS |
| Sessions | Starlette `SessionMiddleware` | signiertes Cookie, `user_id`+`customer_id` |
| Passwort-Hash | `argon2-cffi` (Argon2id) | siehe `07` |
| ORM/DB | SQLAlchemy 2.x + SQLite | `create_all`, WAL |
| Vektor-DB | `qdrant-client` + Qdrant | Cosine, dim 1536, **Collection pro Kunde** |
| Datei-Loader | `pypdf`, `python-docx` | txt/md direkt |
| LLM/Embeddings | `openai` SDK | API-Key aus `.env` |
| Tests | `pytest` + Mocks | keine echten API-Calls |
| Deployment | Docker Compose | `api` + `qdrant`, **Ubuntu** |

## 4. Datenflüsse

### 4.1 Login + Kundenwahl
```text
POST /login → user authentifizieren → session["user_id"]
  erlaubte Kunden = user_customers(user)
  genau 1 → session["customer_id"] automatisch
  mehrere → UI-Auswahl → POST /api/session/customer → session["customer_id"] (mit user∈customer-Check)
```

### 4.2 Ingestion (Text ODER Datei)
```text
POST /api/documents/text {title, text}     |  POST /api/documents (multipart: file[, title])
  → get_current_user + get_current_customer (→403 wenn fremd)                  │
  → (Datei) Typ prüfen (.txt/.md/.pdf/.docx), Größe ≤ 30MB, Filename sanitizen │
            Datei speichern → Loader extrahiert Text → bei Fehler status=failed│
  → ingest_text(customer_id, title, text, source_type, original_filename, ...):
        normalize → chunk → embed → ensure_collection(kb_{cid}) → upsert → Rows
  → 200 {document: {...}}
```

### 4.3 Chat (gescoped)
```text
POST /api/chat {message}
  → get_current_user + get_current_customer
  → agent.run(customer_id, message):
        Tool search_knowledge_base ist fest an kb_{customer_id} gebunden
        loop (≤ MAX_TOOL_ROUNDS): llm.chat(tools) → search(kb_{cid}) → sources
        keine Treffer → No-Context-Text
  → 200 {answer, sources[]}
```
Details: `06_agent_and_rag_design.md`.

## 5. Architektur-Entscheidungen (ADR)

- **ADR-1 — Custom FastAPI** statt fertiger LLM-UI: volle Kontrolle über Login, Tenant, Upload,
  Agent-Loop; sauberer API-Kern; transparenter Handoff. Trade-off: mehr Eigenbau bei der UI.
- **ADR-2 — Agentischer Loop** statt fester Pipeline: Agent entscheidet über Suchen; klarer
  Andockpunkt für weitere Tools. Trade-off: etwas mehr Komplexität → `MAX_TOOL_ROUNDS`.
- **ADR-3 — Qdrant ab MVP**: persistente, skalierbare Suche. Trade-off: ein Container mehr.
- **ADR-4 — Citations deterministisch aus Retrieval**: keine halluzinierten Quellen.
- **ADR-5 (ERSETZT) — ~~eine geteilte KB~~ → eine Qdrant-Collection pro Kunde (`kb_{customer_id}`)**.
  *Begründung:* harte Mandantentrennung, leicht testbar („Kunde A findet nie B"), einfaches Löschen.
  Zusätzlich `customer_id` in SQLite und im Qdrant-Payload als Defense-in-Depth — die *echte*
  Garantie ist aber die physisch getrennte Collection, nicht der Payload-Filter.
- **ADR-6 — Argon2id + signiertes Session-Cookie** (Session hält `user_id`+`customer_id`).
- **ADR-7 (ERSETZT) — ~~Text-only~~ → Text + Datei-Upload** über **einen** `ingest_text()`-Kern;
  Loader (txt/md/pdf/docx) extrahieren nur den Text davor. Keine zweite Ingestion-Pipeline.
- **ADR-8 — OpenAI API-Key** statt OAuth (schnellster offizieller Weg).
- **ADR-9 (NEU) — Tenant-Kontext serverseitig**: aktiver Kunde lebt in der Session; **jede**
  Operation prüft `user ∈ customer` über `get_current_customer`. `customer_id`/Collection-Name
  werden **nie** vom Client übernommen. Das ist das wichtigste, **nicht verhandelbare** Invariant.
- **ADR-10 (NEU) — Dateispeicher** unter `./data/uploads/{customer_id}/{document_id}/{safe_filename}`;
  Filename-Sanitizing, kein Path-Traversal, document-ID als UUID.
- **ADR-11 (NEU) — Entwicklung & Deployment auf Ubuntu**: Coding-Agent arbeitet in Ubuntu (WSL2),
  Deployment auf Ubuntu-Server via Docker Compose. Dev-Prod-Parität by-design; `.gitattributes`
  erzwingt LF, Case-Sensitivity-Disziplin bei Imports/Dateinamen.

## 6. Konfiguration / Environment
Alle Parameter über `.env` (siehe `11`): Modelle, Dimensionen, `TOP_K_DEFAULT`,
`MIN_SCORE_DEFAULT`, `MAX_TOOL_ROUNDS`, `COLLECTION_PREFIX` (Default `kb_`), `MAX_UPLOAD_MB=30`,
`ALLOWED_EXTENSIONS`, `SESSION_SECRET`, OpenAI-Key/Base-URL, DB-/Qdrant-URL. `config.py` failt
beim Start hart, wenn `OPENAI_API_KEY` oder `SESSION_SECRET` fehlen.

## 7. Repo-Struktur

```text
SUP_QA_Helper/
  README.md
  .env.example
  .gitignore
  .gitattributes               # * text=auto eol=lf
  docker-compose*.yml
  docs/                        # Planung + system/ + docs/ (Spiegel 1:1)
  backend/
    Dockerfile
    pyproject.toml
    app/
      __init__.py
      main.py                  # FastAPI + SessionMW + include routers + Exception-Handler
      config.py                # pydantic-settings + fail-fast + allowed_extensions
      db.py models.py          # SQLite + ORM (users, customers, documents, chunks, roles, secrets, kc_* ...)
      auth.py tenant.py        # get_current_user + get_current_customer (Session + 403)
      customers.py             # Registry, user_has, collection_name, global, rename (Qdrant+FS+SQLite)
      routes.py                # HTML + JSON (monolithisch, aber delegiert)
      integration_routes.py    # /api/v1/* (separater Router + Bearer)
      integration_auth.py      # get_integration_user
      knowledge_center.py      # Sources + Contents (ingest/adopt/reject, visibility)
      upload.py                # ingest_combined, inspect, vision, dupe-checks
      ingestion.py             # ingest_text (chunk+embed+upsert+meta)
      document_merge.py        # heuristic + optional LLM Merge für Admin
      duplicates.py            # exact sha256 Stufe 1
      document_fingerprints.py # Stufe 2 + inspect_similarity
      content_hash.py
      document_assets.py
      chats.py users_admin.py system_prompts.py
      roles_admin.py secrets_admin.py
      oauth_device_flow.py     # Device + refresh für chatgpt_oauth
      chunking.py embeddings.py llm.py agent.py retrieval.py prompts.py
      qdrant_store.py          # per-customer collections (InMemory + real)
      loaders/                 # dispatch + text/pdf/docx + vision_ocr + image_inspect + docx_content
      templates/               # layout + chat/kb + admin_* + tools/*
      static/                  # app.js (APP_BOOT) + app.css + brands + vendor
      tests/                   # 25+ Suiten (Isolation Pflicht, alle grün ohne Netz)
  scripts/
    seed_*.py (customers, users, kb, knowledge_center_demo, production, ...)
  data/
    uploads/{customer_id}/...  # + support_kb.sqlite3 (gitignored)
```

Siehe `docs/docs/INDEX.md` (vollständige Spiegel-Liste) und `system/09_module_dependency_map.md` (aktuelle Abhängigkeiten).

## 8. Grenzen & bewusste Vereinfachungen
- Single-Worker-Uvicorn (SQLite-Locking), WAL aktiv.
- Upload bis `MAX_UPLOAD_MB=30` **synchron** verarbeitet; Background-Jobs sind Roadmap.
- Collections **lazy** je Kunde; Suche gegen leere/nicht existierende Collection → **0 Treffer**,
  kein Fehler.
- Kein Caching, kein Pool-Tuning, keine Admin-UI im MVP.

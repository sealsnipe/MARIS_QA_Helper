# 03 — Architektur

**Stand:** 2026-06-03 · **Status:** verbindlich für MVP

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
  docker-compose.yml
  docs/                        # diese Planungsdokumente
  backend/
    Dockerfile
    pyproject.toml
    app/
      __init__.py
      main.py
      config.py
      db.py
      models.py                # users, customers, user_customers, documents, chunks
      auth.py                  # Login/Logout, Argon2id, get_current_user
      tenant.py                # get_current_customer (user∈customer → 403)
      customers.py             # Kunden-Registry-Zugriff
      routes.py
      loaders/
        __init__.py            # dispatch nach Extension
        text_loader.py         # .txt/.md
        pdf_loader.py          # pypdf
        docx_loader.py         # python-docx
      ingestion.py
      chunking.py
      embeddings.py
      llm.py
      agent.py
      prompts.py
      qdrant_store.py
      templates/
        base.html  login.html  index.html
      static/
        app.css  app.js
      tests/
        conftest.py
        test_chunking.py
        test_auth.py
        test_loaders.py
        test_ingestion.py
        test_agent.py
        test_tenant_isolation.py
  scripts/
    seed_customers.py
    seed_users.py              # inkl. user↔customer-Zuordnung
    seed_kb.py                 # Demo-Wissen pro Kunde
  data/
    uploads/                   # {customer_id}/{document_id}/{file}
    support_kb.sqlite3         # gitignored
```

## 8. Grenzen & bewusste Vereinfachungen
- Single-Worker-Uvicorn (SQLite-Locking), WAL aktiv.
- Upload bis `MAX_UPLOAD_MB=30` **synchron** verarbeitet; Background-Jobs sind Roadmap.
- Collections **lazy** je Kunde; Suche gegen leere/nicht existierende Collection → **0 Treffer**,
  kein Fehler.
- Kein Caching, kein Pool-Tuning, keine Admin-UI im MVP.

# 13 — Coding-Agent-Brief (Handoff)

**Stand:** 2026-06-02 · **Adressat:** der bauende Coding-Agent (arbeitet in Ubuntu)
**Status:** verbindliche Bau-Anweisung

---

## 0. TL;DR

Baue **SUP_QA_Helper**: eine selbst gehostete, **mandantengetrennte**, agentengestützte RAG-Web-App
(FastAPI + Jinja2 + Qdrant + SQLite + OpenAI) mit **Login**, Wissensaufnahme per **Text und
Datei-Upload** und **belegten** Antworten — **pro Kunde isoliert**. Die vollständige Spezifikation
liegt in `docs/`. Baue strikt nach `docs/09_implementation_plan.md` (Meilensteine **M1–M7**).
**Halte nach M2 und nach M5 an** und warte auf Review. **Tenant-Isolation** und **Upload-Sicherheit**
sind nicht verhandelbar. **Keine echten API-Calls in Unit-Tests.**

## 1. Auftrag

Implementiere das in `docs/` beschriebene Produkt vollständig und lauffähig (`docker compose up
--build` auf Ubuntu), mit grüner Testsuite (ohne Netz) und erfüllten Abnahme-Gates (§7). Die Docs
sind die **Quelle der Wahrheit** — nicht dieses Brief-Dokument ersetzt sie, es steuert nur das *Wie*
des Vorgehens.

## 2. Pflichtlektüre vor dem ersten Commit

Lies in dieser Reihenfolge, bevor du Code schreibst:
1. `README.md` — Kernentscheidungen, Glossar
2. `01_vision_and_scope.md`, `02_product_requirements.md` — Was & Warum, FR/NFR, Akzeptanz
3. `03_architecture.md` — Aufbau, ADRs, **Repo-Struktur (§7)**
4. `04_data_model.md`, `05_api_specification.md` — Schemata & API-Vertrag
5. `06_agent_and_rag_design.md` — Agent-Loop, Tool, **System-Prompt-Wortlaut**, Retrieval
6. `07_auth_and_security.md` — Login, `get_current_customer`, Upload-Sicherheit
7. `08_ui_ux_design.md` — Seiten, Wireframes, Zustände
8. `09_implementation_plan.md` — **dein Fahrplan**: Tasks T1–T20, Meilensteine, Rollback-Regeln
9. `10_testing_strategy.md`, `11_setup_and_operations.md` — Tests, Env, Seed, Betrieb

## 3. Nicht verhandelbare Invarianten

Diese Punkte **niemals** „vereinfachen" oder weglassen:

1. **Tenant-Isolation (oberste Priorität).**
   - Der aktive `customer_id` kommt **ausschließlich serverseitig aus der Session** (`get_current_customer`),
     **nie** aus Request-Body/Query/Pfad und **nie** vom Modell.
   - Jede Ingestion/Suche/Chat/Delete prüft `user ∈ customer` → sonst **403 `forbidden_customer`**.
   - Daten liegen physisch getrennt in **`kb_{customer_id}`** (eine Qdrant-Collection pro Kunde).
   - Das Such-Tool `search_knowledge_base` ist **fest an `kb_{customer_id}` gebunden**; `customer_id`
     ist **kein** Tool-Parameter.
   - `collection_name()` validiert den Slug (`[a-z0-9_-]+`) — nie roher Client-Input.
2. **Upload-Sicherheit.** Extension-Allowlist (`.txt/.md/.pdf/.docx`), Größe ≤ `MAX_UPLOAD_MB`,
   Filename-Sanitizing (kein Path-Traversal), Speicherpfad serverseitig aus `customer_id`+UUID.
   Leere/kaputte Extraktion → Dokument `status=failed`, **nichts** in Qdrant (`422`).
3. **Citations nur aus Retrieval** — nie aus freiem Modelltext.
4. **Tests ohne Netz** — OpenAI + Qdrant in Unit-Tests **gemockt**, deterministisch.
5. **Keine Secrets im Repo** — `.env` nur mit Platzhaltern; `config.py` failt hart bei fehlendem
   `OPENAI_API_KEY`/`SESSION_SECRET`.

## 4. Arbeitsverzeichnis & Git

- Arbeite in **`~/projects/SUP_QA_Helper`** (Ubuntu, Linux-FS). `docs/` ist bereits vorhanden.
- `git init`, Branch **`main`**. **Erster Commit nach M1**, danach **ein Commit pro Meilenstein**
  (aussagekräftige Messages, z. B. `M2: customers + tenant context`).
- **`.gitignore`** (mindestens):
  ```gitignore
  .env
  data/
  __pycache__/
  .venv/
  *.pyc
  ```
- **`.gitattributes`**:
  ```gitattributes
  * text=auto eol=lf
  ```
- Linux ist **case-sensitiv** — Imports/Dateinamen exakt schreiben.

## 5. Tech-Pins & Setup (siehe `03` §3, `11`)

- **Python 3.12**, FastAPI + Uvicorn (**ein** Worker — SQLite-Locking, WAL aktiv), Jinja2.
- Libs: `fastapi`, `uvicorn[standard]`, `jinja2`, `python-multipart`, `sqlalchemy>=2`, `qdrant-client`,
  `openai`, `argon2-cffi`, `pypdf`, `python-docx`, `pytest`. Sessions via Starlette `SessionMiddleware`.
- **Docker Compose**: Services `api` + `qdrant`, Port **8088**, `restart: unless-stopped`,
  Volume `./data:/app/data`.
- **Modelle aus `.env`** (nicht hardcoden): `CHAT_MODEL` Default `gpt-4.1-mini`,
  `EMBEDDING_MODEL=text-embedding-3-small`, `EMBEDDING_DIM=1536`.
  *Bei Modell-Fehler (404/Zugriff): `CHAT_MODEL=gpt-4o-mini` in `.env` — kein Code-Change.*
- `.env.example` mit allen Variablen aus `11` §3 (Platzhalter für Secrets).

## 6. Bauablauf — Meilensteine (strikt nach `09`)

Arbeite **M1 → M7** in Reihenfolge, Tasks **T1–T20** wie spezifiziert.

- **▶ STOPP nach M2** (Kunden-Fundament): melde dich zum Review, **bevor** du mit Ingestion (M3) beginnst.
- **▶ STOPP nach M5** (Agent & Chat): melde dich zum Review; danach ist ein **manueller Smoke mit
  echtem Key** durch den Menschen vorgesehen (du baust bis dahin gegen Mocks/Platzhalter).
- Zwischen den Stopps darfst du durchlaufen. **Nicht** über einen Stopp hinaus weiterbauen ohne Go.
- Beachte die **Rollback-Regeln** (`09` §4): nie Erfolg melden, wenn Indexierung unvollständig.

## 7. Definition of Done / Abnahme-Gates

Fertig, wenn (vgl. `02` §5, `09` §3, `10`):
1. **Gate 1 — Upload+Antwort:** Nutzer/Kunde `acme` lädt PDF → Frage → Antwort **mit Quelle aus dem Dokument**.
2. **Gate 2 — Isolation:** Nutzer/Kunde `globex` sieht **keine** `acme`-Dokumente; Chat findet **nichts**
   aus `acme`; Zugriff auf fremden Kunden → **403**.
3. **Gate 3 — Extraktion:** kaputtes/leeres PDF → `status=failed`, klare UI-Meldung, **nichts** in Qdrant.
4. `pytest` **grün ohne Netz**; **Tenant-Isolation-Tests grün** (`test_tenant_isolation.py`, Pflicht).
5. `docker compose up --build` aus sauberem Checkout; keine Secrets im Repo.

## 8. Verhalten bei Unklarheiten

- Bei Lücken: **dokumentierten Default** wählen (Docs + dieser Brief). Bei **Widersprüchen oder
  echten Lücken**: **anhalten und melden**, nicht still etwas erfinden, das Scope/Invarianten berührt.
- **Kanonische Entscheidungen (Schnellreferenz):**

  | Thema | Wert |
  |---|---|
  | Collection | `kb_{customer_id}` (Prefix aus `COLLECTION_PREFIX`, Default `kb_`) |
  | Vektor | dim 1536, Cosine |
  | Aktiver Kunde | aus `session["customer_id"]`, Check `user ∈ customer` → sonst 403 |
  | Demo-Kunden | `acme` (Acme GmbH), `globex` (Globex AG) |
  | Demo-Nutzer | 1 Nutzer mit beiden Kunden + 1 Nutzer mit nur `globex` |
  | Dateitypen | `.txt`, `.md`, `.pdf`, `.docx`; max `MAX_UPLOAD_MB=30` |
  | Ingestion-Kern | `ingest_text(customer_id, title, text, source_type, ...)` (Loader nur davor) |
  | Dependencies | `get_current_user`, `get_current_customer` |
  | Fehlercodes | 401 not_authenticated, 403 forbidden_customer, 400 unsupported_file_type/empty_*, 413 file_too_large, 422 extraction_failed, 502 embedding_failed/vector_store_failed/llm_failed |
  | Sprache | UI + Antworten Deutsch; Code/Bezeichner Englisch |

## 9. Konkrete erste Schritte (M1)

1. Repo-Skelett gemäß `03` §7 anlegen; `.gitignore`, `.gitattributes`, `git init`, Branch `main`.
2. `backend/pyproject.toml` (Libs §5), `backend/Dockerfile`, `docker-compose.yml` (api+qdrant, 8088).
3. `app/config.py` (typisierte Settings aus `.env`, **Fail-fast** bei `OPENAI_API_KEY`/`SESSION_SECRET`).
4. `app/main.py` mit `GET /api/health` → `{"ok": true}`.
5. `app/db.py` + `app/models.py` (`users`), `create_all`, WAL.
6. `app/auth.py` (Argon2id, `SessionMiddleware`, Login/Logout, `get_current_user`), `templates/login.html`.
7. `scripts/seed_users.py`. **Verifizieren:** `docker compose up --build`, Health grün, Login mit Seed-User.
8. Commit `M1: skeleton, health, auth`. → dann M2, **danach STOPP**.

## 10. Was bei jedem Stopp (M2, M5) zu liefern ist

- Kurzbericht: erledigte Tasks, erfüllte Done-Kriterien, getroffene Annahmen.
- Testlauf-Ausgabe (`pytest`), Bestätigung „ohne Netz grün".
- Offene Fragen/Widersprüche (falls vorhanden).
- **Nicht** weiterbauen über den Stopp hinaus ohne ausdrückliches Go.

## 11. Do-NOT-Liste

- ❌ `customer_id`/Collection-Name aus Client-Input übernehmen oder als Tool-Parameter führen.
- ❌ Mandanten-Trennung über bloßen Payload-Filter „lösen" (getrennte Collections sind Pflicht).
- ❌ Leere/kaputte Extraktion still indexieren.
- ❌ Nur Vektoren speichern — Chunk-Text gehört in Qdrant-Payload **und** SQLite.
- ❌ Quellen aus dem Modelltext statt aus Retrieval bilden.
- ❌ Echte OpenAI-/Qdrant-Calls in Unit-Tests.
- ❌ `.env`, `data/` oder Secrets committen.
- ❌ Modellnamen hardcoden (immer aus `.env`).
- ❌ Über einen Review-Stopp (M2, M5) hinaus weiterbauen ohne Go.

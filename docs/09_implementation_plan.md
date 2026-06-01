# 09 — Implementierungsplan

**Stand:** 2026-06-02 · **Status:** verbindlich für MVP

Abhängigkeitsgeordnete Tasks für den Coding-Agent. Reihenfolge = Build-Reihenfolge.
**Kundenfundament vor Ingestion; Tenant-Isolation + Upload sind nicht verhandelbare Invarianten.**

---

## 1. Meilensteine

| MS | Inhalt | Tasks | Review-Stopp |
|---|---|---|---|
| **M1 — Gerüst & Login** | App startet (Ubuntu/Docker), Health, Auth, Session, Seed-User | T1–T4 | — |
| **M2 — Kunden-Fundament** | `customers`+`user_customers`, Seed, `get_current_customer`, Kundenwahl | T5–T7 | ✅ **Stopp** |
| **M3 — Ingestion-Kern (scoped)** | Qdrant pro Kunde, Chunking, Embeddings, `ingest_text`, Text-Endpoint, Liste, Delete | T8–T12 | — |
| **M4 — Datei-Upload** | Loader (txt/md/pdf/docx), Multipart-Endpoint, Dateispeicher, `failed`-Pfad | T13–T14 | — |
| **M5 — Agent & Chat (scoped)** | Prompts, LLM, Agent-Loop an Kunde gebunden, Chat-Endpoint | T15–T17 | ✅ **Stopp + Smoke** |
| **M6 — UI** | Login, Kundenauswahl, KB Text/Datei-Tabs, Chat, Zustände | T18 | — |
| **M7 — Isolation & Abnahme** | Tenant-Isolation-Tests (Pflicht), Upload/Loader-Tests, README, Seed, Abnahme | T19–T20 | — |

## 2. Tasks

### M1 — Gerüst & Login
- **T1 — Projektgerüst & Health.** Repo-Struktur (`03` §7), FastAPI, Docker Compose, Health.
  Dateien: `docker-compose.yml`, `.env.example`, `.gitignore`, `.gitattributes` (`* text=auto eol=lf`),
  `backend/Dockerfile`, `backend/pyproject.toml`, `app/main.py`, `app/config.py`.
  Done: `docker compose up --build` startet `api`+`qdrant`; `GET /api/health`→`{"ok":true}`;
  `config.py` Fail-fast bei fehlendem `OPENAI_API_KEY`/`SESSION_SECRET`.
- **T2 — Persistenz-Basis.** `db.py`, `models.py` (`users`; weitere Modelle in M2/M3), `create_all`, WAL.
  Done: Tabellen beim Start, idempotent.
- **T3 — Auth.** `auth.py` (Argon2id, `get_current_user`), `SessionMiddleware`, Login/Logout,
  `login.html`. Done: geschützte Route ohne Session → Redirect/401; korrekter Login → Session;
  generische Fehlermeldung; Logout.
- **T4 — Seed-User (Basis).** `scripts/seed_users.py` (Nutzer + Argon2id). Done: idempotent; Login klappt.

### M2 — Kunden-Fundament  ▶ Review-Stopp
- **T5 — Kunden-Modelle.** `customers`, `user_customers` in `models.py`; `customers.py` (Registry-Zugriff,
  erlaubte Kunden je Nutzer). Done: Tabellen vorhanden; Slug-Validierung `[a-z0-9_-]+`.
- **T6 — Seed Kunden + Zuordnung.** `scripts/seed_customers.py` (`acme`,`globex`); `seed_users.py`
  um `user_customers` erweitern (1 Nutzer mit 2 Kunden + 1 Nutzer mit 1 Kunden). Done: idempotent.
- **T7 — Tenant-Kontext.** `tenant.py` (`get_current_customer`: Session + `user∈customer` → 403);
  `GET /api/customers`; `POST /api/session/customer`; Auto-Set bei genau 1 Kunden beim Login.
  Done: fremder Kunde → 403; Wechsel setzt Session; 1-Kunden-Nutzer automatisch aktiv.
  **▶ STOPP: Review des Kundenfundaments vor Ingestion.**

### M3 — Ingestion-Kern (scoped)
- **T8 — Qdrant-Store (parametrisiert).** `qdrant_store.py`: `collection_name(cid)` (validiert),
  `ensure_collection`, `upsert/search/delete` je Kunde; Suche gegen leere Collection → `[]`.
  Done: Vertrag aus `04` §2.3; nie roher Client-Collection-Name.
- **T9 — Chunking.** `chunking.py` + `tests/test_chunking.py`. Done: Größe/Overlap/keine leeren.
- **T10 — Embeddings.** `embeddings.py` (batched, mockbar). Done: mit Key (manuell) ok; in Tests gemockt.
- **T11 — Ingestion-Service.** `documents`+`chunks`-Modelle (mit `customer_id`); `ingestion.py`:
  `ingest_text(customer_id, title, text, source_type, original_filename=None, ...)`:
  normalize→chunk→embed→`ensure_collection`→`upsert`→Rows. `tests/test_ingestion.py`.
  Done: Erfolg schreibt korrekte Rows+Points (gemockt); Embedding-/Upsert-Fehler → kein `indexed`-Doc.
- **T12 — Dokument-Endpoints (Text).** `POST /api/documents/text`, `GET /api/documents`,
  `DELETE /api/documents/{id}` — alle über `get_current_customer` gescoped, Tenant-Check.
  Done: Einpflegen/Liste/Löschen nur für aktiven Kunden; fremd → 403/404.

### M4 — Datei-Upload
- **T13 — Loader-Schicht.** `loaders/` (txt/md direkt, pdf via `pypdf`, docx via `python-docx`),
  Dispatch nach Extension; leeres/kaputtes → Fehler. `tests/test_loaders.py`.
  Done: txt/md/pdf/docx → Text; leeres PDF → klarer Fehler (kein leerer Text).
- **T14 — Upload-Endpoint.** `POST /api/documents` (Multipart): Typ-Allowlist, Größe ≤
  `MAX_UPLOAD_MB`, Filename-Sanitizing, Speicherpfad `./data/uploads/{customer_id}/{document_id}/`,
  Loader → `ingest_text(...)`; Extraktionsfehler → `status=failed`, nichts in Qdrant.
  Done: PDF-Upload landet in `kb_{cid}`; falscher Typ→400; zu groß→413; kaputt→422+`failed`.

### M5 — Agent & Chat (scoped)  ▶ Review-Stopp + Smoke
- **T15 — Prompts & LLM-Client.** `prompts.py` (System-Prompt + `NO_CONTEXT_TEXT`, Wortlaut `06`),
  `llm.py` (Tool-Calling, mockbar).
- **T16 — Agent-Loop.** `agent.py`: `run(customer_id, message, top_k)`, Tool an `kb_{cid}` gebunden,
  Citation-Aggregation, `MAX_TOOL_ROUNDS`, No-Context. `tests/test_agent.py`.
  Done: Tests (gemockt): Tool→Antwort+Quellen aus Retrieval; keine Treffer→No-Context; Max-Runden.
- **T17 — Chat-Endpoint.** `POST /api/chat` (gescoped) → `{answer, sources, no_context}`.
  Done: geschützt+scoped; leere Message→400.
  **▶ STOPP: Review + manueller Smoke mit echtem Key (Seed-KB, echte Frage) vor UI.**

### M6 — UI
- **T18 — UI.** `templates/` (base, login, index), `static/app.css`, `static/app.js`, HTML-Routen.
  Kundenauswahl im Header, KB Text/Datei-Tabs + Dropzone, Dokumentliste, Chat, alle Zustände (`08`).
  Done: Login funktioniert; Kunde wählbar; Text+Datei einpflegen; fragen; Quellen sichtbar; Zustände da.

### M7 — Isolation & Abnahme
- **T19 — Tests.** `tests/test_tenant_isolation.py` (**Pflicht**), Upload-/Loader-/Agent-/Ingestion-Tests.
  Done: Isolation-Gates grün (s. u.); gesamte Unit-Suite ohne Netz grün.
- **T20 — README, Seed, Abnahme.** `README.md` (Setup/Run/Seed, Ubuntu), `scripts/seed_kb.py`
  (Demo-Wissen pro Kunde, deutlich unterscheidbar), Akzeptanz durchspielen.
  Done: `docker compose up` aus sauberem Checkout; Abnahme-Gates erfüllt.

## 3. Abnahme-Gates (Pflicht, vgl. `02`§5 / `10`)
1. **Upload+Antwort:** Nutzer/Kunde `acme` lädt PDF → Frage → Antwort **mit Quelle aus dem Doc**.
2. **Isolation:** Nutzer/Kunde `globex` sieht **keine** `acme`-Doks; Chat findet **nichts** aus `acme`;
   fremder Kunde → 403.
3. **Extraktion:** kaputtes/leeres PDF → `status=failed`, klare Meldung, **nichts** in Qdrant.

## 4. Kritische Rollback-Regeln (Ingestion/Upload)
- Datei-Extraktion leer/kaputt → `status='failed'`, kein Embedding, nichts in Qdrant (`422`).
- Embedding-Fehler → kein `indexed`-Doc (`502 embedding_failed`).
- Upsert-Fehler → kein `indexed`-Doc; teilweise geschriebene Points best-effort entfernen (`502`).
- Niemals Erfolg melden, wenn Indexierung unvollständig.

## 5. Definition of Done (gesamt)
Alle Task-Done erfüllt; `pytest` grün ohne echte API-Calls; **Tenant-Isolation-Tests grün**;
Abnahme-Gates (§3) erfüllt; keine Secrets im Repo; `docker compose up --build` reproduzierbar auf Ubuntu.

## 6. Grobschätzung
M1 ~0.5 T · M2 ~1 T · M3 ~1.5 T · M4 ~1 T · M5 ~1 T · M6 ~1 T · M7 ~0.5–1 T.
Gesamt **~6–8 fokussierte Tage** (Upload + Mandanten + Isolation-Tests).

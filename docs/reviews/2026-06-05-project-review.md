# Projekt-Qualitätsreview — 2026-06-05

**Branch:** `review/project-quality-2026-06`  
**Reviewer:** (automatisiert + manuell via Coding-Agent + Mensch)  
**Scope:** Read-only (kein Code-Change in Phase 2)  
**Basis:** `docs/13_coding_agent_brief.md` (Invarianten), `docs/10_testing_strategy.md`, `docs/DOCUMENTATION_RULES.md`, `docs/system/*`, `docs/03_architecture.md` §7, `docs/15_implementation_status.md`, `docs/05_api_specification.md`  
**Vorgehen:** 
- `python3 -m pytest` (via Docker-Image, ohne Netz, Mocks) — Fokus Isolation + neue Suiten.
- Statische Code-Inspektion (tenant, upload, agent, retrieval, qdrant, routes, main, admin/*, integration/*).
- Vergleich Plan vs. Ist (Struktur, Doku-Spiegel, Querschnitt).
- Keine Style-/LOC-/Legacy-Bewertung.

**Zusammenfassung:** Keine Blocker für Invarianten gefunden. Tests vollständig grün. Doku-Drift (25 fehlende Spiegel) ist das zentrale Thema. Refactoring nicht erforderlich (Gate A).

---

## Kritisch (müssen vor Merge / in diesem Review-Zyklus adressiert werden)

### 1. Doku-Pflicht-Verletzungen (25 fehlende Spiegel unter `docs/docs/`)
Per `DOCUMENTATION_RULES.md` §3.1 / §7 / §9: Neue Fachlogik-Dateien **müssen** im selben Change einen Spiegel erhalten. Verstoß gegen "Code = Quelle der Wahrheit".

**8 Module (backend/app/):**
- `document_merge.py` (Merge-Logik, LLM-gestützt)
- `duplicates.py` (content_sha256 + Fingerprint-Duplikat-Erkennung)
- `integration_auth.py` (Bearer-Token, Integration-User)
- `integration_routes.py` ( /api/v1/ask + /knowledge-content )
- `knowledge_center.py` (Content-Vorschläge, Adopt/Reject, Ingest)
- `oauth_device_flow.py` (Codex/ChatGPT OAuth Device Flow für Keys-Admin)
- `roles_admin.py` (Rollen-CRUD + auto_add + Presets)
- `secrets_admin.py` (DB-Secrets + Masking + effective Secrets für Chat/Embed/Similarity/Integration)

**11 Tests:**
- `test_admin_keys.py`
- `test_admin_roles.py`
- `test_document_fingerprints.py`
- `test_document_merge.py`
- `test_docx_content.py`
- `test_duplicate_detection.py`
- `test_image_inspect.py`
- `test_integration_api.py`
- `test_knowledge_center.py`
- `test_selective_vision.py`
- `test_vision_ocr.py`

**5 Templates:**
- `admin_keys.html`
- `admin_roles.html`
- `tools/bild_zu_text.html`
- `tools/knowledge_center_content.html`
- `tools/knowledge_center_sources.html`

**1 Script:**
- `scripts/seed_knowledge_center_demo.py`

**Zusätzlich (für INDEX + Vollständigkeit):**
- Vorhandene Spiegel (z. B. `document_fingerprints.md`, `document_assets.md`, `content_hash.md`, `test_admin_keys.md` existieren teilweise) sind **nicht** in `docs/docs/INDEX.md` gelistet.
- `docs/docs/backend/app/tests/` spiegelt nicht alle `test_*.py` (s.o.).

**Empfohlene Behebung (Phase 3 A):** Alle 25 + INDEX-Update in diesem Branch nachziehen (kein Refactor). Siehe Phase-3-Sync-Plan.

### 2. Veraltete Querschnitts-/Architektur-Doku (Drift)
- **`docs/03_architecture.md` §7 (Repo-Struktur):** Stark veraltet (Stand ~MVP).
  - Listet alte Loader-Namen (`text_loader.py` vs. `text_loaders.py` + `docx_content.py` etc.).
  - Fehlt: `tenant.py` explizit (wird erwähnt in §2), `document_*`, `duplicates`, `document_merge`, `integration_*`, `knowledge_center`, `oauth_device_flow`, `roles_admin`, `secrets_admin`, `users_admin`, `chats`, `system_prompts`, `upload`, viele Tests, Vision/OCR-Loader, `document_assets`/`fingerprints`, `content_hash`, Templates unter `tools/`, `admin_keys`/`admin_roles`.
  - Aktuelle Struktur (main.py Router + separate integration_router, Modulgrenzen) nicht abgebildet.
- **`docs/system/09_module_dependency_map.md`:** Veraltet (Stand 2026-06-03).
  - Nur grobe 5-Schichten (UI / Anwendung / RAG / Infra / Plattform).
  - Fehlende Abhängigkeiten/Module: `document_merge`, `duplicates`, `document_fingerprints`, `document_assets`, `content_hash`, `integration_auth`/`routes`, `knowledge_center`, `oauth_device_flow`, `roles_admin`, `secrets_admin`, `users_admin`, `system_prompts`, `chats`, `upload`, Vision-Loader, `image_inspect` etc.
  - Keine Traces zu neuen Admin-Flows, Global-Customer, Duplikat-Checks, Knowledge-Center, Integration.
  - Entry-Points ok, aber unvollständig.
- **API-Docs (`docs/05_api_specification.md`):** Teilweise aktuell (erwähnt /api/v1/*, /admin/roles, /admin/keys, Knowledge-Center-Tools), aber:
  - Keine detaillierten Request/Response-Schemas oder Fehler-Codes für neue Admin-Endpoints (Rollen, Keys mit OAuth-Device-Flow).
  - `system/12_integration_api.md` wird referenziert — prüfen ob vollständig.
  - Mandant-Invariant wird korrekt beschrieben, aber neue globale/scope-Logik (global + assigned) nicht tief.
- **Weitere bekannte (aus `15`):** 03, 05, 08, 14 empfohlen zu aktualisieren; 01/02/04/06/07/09/10/11/12/13 teilweise ok.

**Auswirkung:** Verletzt "Spiegel + Querschnitt" + "15 vs. Code". Neue Entwickler/Agents bekommen falsches Bild von Struktur und Abhängigkeiten.

### 3. Fehlende / unvollständige Spiegel-Index-Pflege
- `docs/docs/INDEX.md` listet nicht alle existierenden Spiegel (z. B. `document_fingerprints.md` fehlt im Listing, viele neue Tests/Loader).
- "Hälfte A/B"-Tracking (Cursor/Grok) ist historisch, aber unvollständig für Post-MVP-Features (Vision, Duplikate, Knowledge Center, Admin-Rollen/Keys, Integration).

---

## Empfohlen später (nicht kritisch für diesen Zyklus; nice-to-have / zukünftige PRs)

- **system/09** + **03 §7** + **INDEX.md** + **15_status** aktualisieren (wird in Phase 3 A mit den Spiegeln gemacht).
- **Weitere Plan-Docs** (01–14) nur bei Bedarf / nächster inhaltlicher Änderung updaten (explizit **nicht** vollständiges Update aller in diesem Review verlangt).
- **system/06_admin_flows.md** und **07_ui_map.md**: Stand 2026-06-05, erwähnen bereits admin_roles/admin_keys/tools/* — "teils aktuell", geringe Lücken (z. B. genaue Error-Codes oder JS-Init-Details) können bei Spiegel-Pflege mitgezogen werden.
- **system/10_testing_landscape.md**, **12_integration_api.md**, **08_data_model_sync.md**: Stichproben grün, aber nach Sync der fehlenden Test-Spiegel auf Vollständigkeit prüfen.
- **Automatisierung (langfristig, aus DOCUMENTATION_RULES §10):** CI-Check "Code-Datei ohne Spiegel" + ADR-Prozess. Nicht Teil dieses Reviews.
- **Kleine Beobachtungen (keine Blocker):**
  - `routes.py` delegiert sauber (upload/ingest, admin via get_admin_user, integration separat).
  - `main.py` ist dünn (Lifespan + Router-Mount + Exception-Handler) — gute Trennung.
  - Neue Module (`knowledge_center`, `integration_routes`, `roles_admin` etc.) bilden klare Domänen-Grenzen (keine Zirkelabhängigkeiten zu routes).
  - Duplikat-Logik (fingerprints + content-hash) ist isoliert und vor Ingestion geprüft.
  - Vision/OCR-Loader sauber gekapselt (optional, fallback bei Fehlern).

---

## Bewusst ignoriert (per Review-Auftrag — nicht bemängeln)

- Zeilenzahl `routes.py` (~1844 LOC) und `backend/app/static/app.js` (~3376 LOC) — monolithisch, aber OK (Tests grün; klare Funktions-/Modulgrenzen; keine "Gott-Klasse"-Probleme bei Isolation/Fehlerpfaden).
- Style / Formatting / Naming-Konsistenz (außer wo Invarianten betroffen).
- Legacy `index.html` (existiert, wird nicht mehr primär genutzt; Redirects in routes/main).
- Vollständiges Update **aller** 01–14 Planungsdokumente (nur die genannten Drift-Punkte + Spiegel/Querschnitt/Status in Scope).
- Nicht geprüft: Performance, konkrete UI-Screenshots, manuelle Smoke mit echtem Key (außer via pytest-Smoke-Logik), OAuth-Device-Flow End-to-End (nur statisch + Integration-Tests), Drittanbieter (qdrant, openai SDK).
- Keine neuen Features oder Refactors implementiert (read-only Review).

---

## Geprüfte Invarianten (aus `13_coding_agent_brief.md` §3 + §7 + `10`)

### Tenant-Isolation (Session-Mandant + Collections)
- `tenant.py`: `get_current_customer` zieht **ausschließlich** `request.session["customer_id"]`, prüft `user_has_customer`, active, dann 403 + Session-Cleanup.
- `customers.py`: `collection_name` validiert Slug (`^[a-z0-9_-]+$`); `user_has_customer` behandelt Admin + Global + normale Zuordnungen korrekt; `GLOBAL_CUSTOMER_ID="global"` speziell.
- `routes.py`: Alle content/chat-Routen nutzen `Depends(get_current_customer)`; Session-Set `/api/session/customer` prüft `user_has_customer` → 403.
- `retrieval.py` + `agent.py`: `search_knowledge_base_scoped` / `search_knowledge_base_all` für global/scope; Tool-Call **nie** mit customer_id als Param.
- `qdrant_store.py` + `InMemory...`: Nutzt `collection_name(customer_id)` (validiert); separate Buckets/Collections pro Kunde.
- `test_tenant_isolation.py` + `test_global_customer.py` + Integration-Suiten: Alle 5 Pflicht-Szenarien abgedeckt (getrennte Collections, scoped Search, 403 auf fremd, validate slug).
- **Ergebnis:** Invariante gehalten. Keine Stelle, wo client-seitiges customer_id direkt trusted wird (außer explizit in Integration-API, die eigenen User + active-Check hat und scope=[id] erzwingt).

### Upload + Extraktion + Duplikate
- `upload.py`: `_validate_upload_file` (Extension aus Settings + Size), `sanitize_filename`, Storage unter `customer_id/doc_id/`.
- Bei LoaderError / short text nach extract: `_discard_stored_upload` + `UploadError("extraction_failed")` / "empty_text" — **kein** ingest.
- Duplikat: `find_duplicate_document` + `inspect_similarity_payload` (content_sha256 + fingerprints) **vor** `ingest_text`; `allow_duplicate` Flag nur bei explizitem UI-Confirm.
- Routes: `inspect_upload`, `ingest_combined` immer hinter Tenant-Check.
- `test_upload_api.py`, `test_duplicate_detection.py`, `test_document_fingerprints.py`, `test_loaders.py`: Abdeckung inkl. failed-Status, no-index.
- **Ergebnis:** Sicherheits- + Fail-Invarianten gehalten.

### Citations nur aus Retrieval
- `agent.py`: `SourceRegistry` sammelt nur aus `search_knowledge_base*` (scoped); finale Sources via `filter_sources_by_answer_citations(registry..., content)` — nie roher LLM-Output.
- Fallbacks: `NO_CONTEXT_TEXT`, leere Sources, `no_context=True`.
- `test_agent.py` + `test_retrieval.py`: Dedup, Citation-Filter, No-Context-Fälle.
- **Ergebnis:** Gehalten (deterministisch aus Retrieval).

### Tests ohne Netz + neue Suiten
- **Gesamtlauf:** `docker compose run --rm --no-deps ... python -m pytest -q` → **155 passed, 0 failed** (23s, nur 1 Deprecation-Warning von TestClient).
- Fokus-Isolation + neue:
  - `test_tenant_isolation.py`, `test_global_customer.py` → grün.
  - `test_knowledge_center.py`, `test_integration_api.py` → grün (56 Tests in ausgewählten Suiten).
  - `test_admin_roles.py`, `test_admin_keys.py` (via full), `test_document_merge.py`, `test_duplicate_detection.py`, `test_document_fingerprints.py`, Vision/OCR/Inspect-Suiten → alle grün.
- Mocks: `conftest.py` setzt Test-Env **vor** Imports; `fake_embeddings`, `fake_vector_store` (InMemory pro Collection), `db_session` tmp SQLite, autouse.
- Keine echten OpenAI/Qdrant-Calls in Unit-Tests.
- **Ergebnis:** 100% grün, Isolation + Post-MVP-Suiten vollständig und deterministisch. Keine Netz-Abhängigkeit.

### Admin / Secrets / Rollen — nur Berechtigungen & Fehlerpfade
- `auth.py`: `get_admin_user` = `get_current_user` + `if not user.is_admin: raise ForbiddenError()` (→ 403 "forbidden").
- `routes.py`: Admin-HTML-Seiten (`/admin/roles`, `/admin/keys` etc.) via `_admin_page_redirect` + `user.is_admin`; API via `Depends(get_admin_user)`.
- `roles_admin.py` / `secrets_admin.py`: Eigene `*AdminError` (mit code/status/detail); Validierungen (forbidden_customer für global, invalid_*, unknown_*); keine Business-Logik außerhalb Admin-Module.
- Routes-Handler: Error-Handler in `main.py` für `RoleAdminError`, `SecretsAdminError`, `CustomerAdminError`, `UserAdminError`, `KnowledgeCenterError` etc. → sauberes `{"error": code, "detail"?}`.
- Keine Privilege-Escalation-Pfade gefunden (z. B. non-admin kann keine Rollen ändern; Integration-User ist separater nicht-admin User).
- **Ergebnis:** Nur Berechtigungen + Fehlerpfade geprüft — sauber, keine Lücken in den Admin-Grenzen.

### Struktur: main.py Router, Modul-Grenzen
- `main.py`: Lifespan (init_db + ensure_global + default_prompt), SessionMiddleware, `include_router(router)` (aus `routes`) + `include_router(integration_router)`, Static-Mount, **ausschließlich** Exception-Handler (saubere Trennung).
- `routes.py`: ~1844 LOC, aber gut organisiert (Auth-Helpers, Page-Handler, API-Handler gruppiert; Delegation an fachliche Module).
- Gute Grenzen beobachtet:
  - `integration_routes.py` + `integration_auth.py`: Vollständig separater Router + Auth (Bearer vs. Session).
  - `knowledge_center.py`: Eigene Error + Ingest-Funktionen, genutzt von Integration + Admin-Routes.
  - `roles_admin`/`secrets_admin`/`users_admin`/`customers.py`: Getrennte CRUD + Validierung.
  - `upload.py` + `ingestion.py` + `duplicates.py` etc.: Klare Pipeline-Stufen.
- Keine Zirkel-Importe oder Gott-Objekte, die Invarianten gefährden.
- **Ergebnis:** Struktur akzeptabel; `routes.py` monolithisch aber wartbar (kein Refactor-Gate-Trigger).

### Sonstige Flows (kurz)
- Global-Customer + Multi-KB-Scope: In `customers.py`, `retrieval.py`, `agent.run(..., scope_customer_ids)`.
- Admin-Kunden-Rename: Zentral in `customers.rename_tenant_customer` (Qdrant-Copy + SQLite-Update + Uploads-Move best-effort) — gut isoliert.
- Vision/OCR: Optional, graceful Degradation (Fehler → spezifische UploadError, kein stilles Indexieren).
- Duplikate (Stufe 1+2): Vor Ingest, mit UI-Warn/Confirm.

---

## Test- und Smoke-Referenz (aus Review-Lauf)

```bash
# Voll (ohne Netz)
docker compose run --rm --no-deps -e OPENAI_API_KEY=... -e SESSION_SECRET=... api python -m pytest -q --tb=no
# 155 passed

# Fokus
... pytest ... test_tenant_isolation.py test_knowledge_center.py test_admin_roles.py test_integration_api.py test_document_merge.py test_duplicate_detection.py test_document_fingerprints.py test_global_customer.py
# 56 passed
```

Manueller Smoke (nicht in diesem Review ausgeführt, aber via `10` §5 + `system/11` dokumentiert): Login → Kunde → Upload (gut/schlecht) → Frage mit Quellen → Wechsel Kunde → Isolation → Delete.

---

## Nächste Schritte (Review-Gate → Phase 3)

1. **Refactor-Gate dokumentieren** (in `PROJECT_STANDARDS.md` + hier): **A — Standard: Kein Code-Refactor**. Alle Spiegel + Querschnitt/Architektur-Sync in diesem Branch.
2. **Phase 3 A ausführen:** 25 Spiegel anlegen (vollständige Vorlage §5 für Fachlogik, §6 für Skripte), `docs/docs/INDEX.md` komplettieren, `system/09_module_dependency_map.md` aktualisieren (neue Module + Traces), `03_architecture.md` §7 + ggf. andere Abschnitte sync, `15_implementation_status.md` updaten (Doku-Stand).
3. **PR:** Kurze Executive Summary (max. ~10 Bullets), Review-MD als Artefakt, alle Spiegel als "Doku-Sync nach Review".
4. Optional (nicht gefordert): Nach Sync einen CI-Dry-Run oder erneuten pytest + manuellen Smoke.

**Kein Blocker identifiziert** — A-Pfad ist ausreichend und risikoarm.

---

**Ende Review.** Stand: 2026-06-05. Alle Prüfpunkte abgedeckt. Invarianten und Tests: ✅. Doku-Drift: Hauptthema, planmäßig in Phase 3 zu beheben.

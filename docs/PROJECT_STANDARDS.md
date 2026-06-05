# Projekt-Standards — MARIS Q/A Helper

**Stand:** 2026-06-05  
**Zweck:** Einheitlicher Einstieg und verbindliche Regeln für Qualität, Doku-Pflege und Refactoring-Entscheidungen. Ergänzt `DOCUMENTATION_RULES.md`, `13_coding_agent_brief.md`, `10_testing_strategy.md`.

---

## Prioritäten (nicht verhandelbar)

1. **Tenant-Isolation** (oberste Invariante, aus `13` §3)
   - Aktiver `customer_id` **ausschließlich serverseitig aus Session** (`get_current_customer`).
   - Niemals aus Client-Input (Body/Query/Path) oder Modell/Tool-Parametern.
   - Jede Operation: `user ∈ customer` → sonst `403 forbidden_customer`.
   - Physisch getrennte Qdrant-Collections `kb_{customer_id}` (validiert via `collection_name`).
   - `search_knowledge_base` fest an aktiven Kunden gebunden.

2. **Upload-Sicherheit** (aus `13`)
   - Allowlist: `.txt,.md,.pdf,.docx,.png,...` (via `ALLOWED_EXTENSIONS` + Images).
   - Größe ≤ `MAX_UPLOAD_MB` (Default 30), Filename-Sanitizing (kein Traversal).
   - Speicher: `./data/uploads/{customer_id}/{doc_uuid}/{safe_name}`.
   - Leere/kaputte Extraktion → `status=failed` (Dokument), **kein** Index in Qdrant (`422 extraction_failed`).

3. **Citations deterministisch aus Retrieval** (nie aus Modelltext)
   - Quellen nur aus `SourceRegistry` / `search_knowledge_base*` + `filter_sources_by_answer_citations`.
   - `NO_CONTEXT_TEXT` bei keinen Treffern.

4. **Tests ohne Netz** (Pflicht, `10` + `13`)
   - OpenAI (Embed/LLM) und Qdrant **gemockt** (Fixtures in `conftest.py`: `fake_embeddings`, `fake_vector_store`, `InMemoryVectorStore`).
   - `pytest` grün deterministisch; `@integration` nur manuell/optional.
   - **Tenant-Isolation-Tests Pflicht** (`test_tenant_isolation.py` + Suiten für global, admin, knowledge, merge, duplicates).

5. **Keine Secrets im Repo**; Fail-fast in `config.py` bei fehlendem `SESSION_SECRET`/`OPENAI_API_KEY`.

6. **Doku als Spiegel der Wahrheit** (`DOCUMENTATION_RULES.md`)
   - Code = Quelle der Wahrheit.
   - Neue Datei → Spiegel `.md` im selben Change (PR).
   - 1:1 Pfad-Mapping unter `docs/docs/`.

---

## Refactoring-Gate

**Entscheidung nach Review (Phase 2):**

- **A (Standard, empfohlen):** Kein Code-Refactor in diesem Review-Branch.
  - Routes.py monolithisch (~1844 LOC) aber funktional stabil (Tests grün, klare Delegation an `upload`, `ingestion`, `agent`, `knowledge_center`, `integration_routes`).
  - Gute Modul-Grenzen bereits vorhanden: `integration_routes.py` + `integration_auth.py`, `knowledge_center.py`, `roles_admin.py`/`secrets_admin.py` (Admin-Logik getrennt), `document_merge.py`/`duplicates.py`.
  - Refactor würde Risiko für Invarianten (Isolation, Upload, Citations) erhöhen ohne sofortigen Nutzen.
  - Stattdessen: **alle Spiegel + Querschnitt sync** (25 fehlende + INDEX + system/09 + 03 §7 + 15_status).

- **B (nur bei Blocker):** Minimal-Refactor (z. B. Aufteilung großer Handler) + Pflicht-Spiegel + pytest in **derselben** Branch. Bisher keine Blocker identifiziert (Tests 155/155 grün, Isolation-Suiten vollständig).

Gate-Dokumentation: siehe `docs/reviews/2026-06-05-project-review.md` (Abschnitt Kritisch / Empfohlen später).

Nach diesem Review: Bei zukünftigen Features **vor Merge** prüfen, ob Modulgrenze reicht oder Refactor fällig (z. B. wenn neue große Domäne wie "Jira-Import" kommt).

---

## Doku-Pflicht (Zusammenfassung `DOCUMENTATION_RULES.md`)

- **Spiegel (Ebene 2):** Immer für `backend/app/*.py` (inkl. tests, loaders), `templates/*.html` (außer vendor), `scripts/*.py` mit Logik, Docker/Compose, pyproject, Root-README, Config-Vorlagen.
- **Kurz-Doku (§6):** Für Betriebsskripte ohne Fachlogik (`start.sh` etc.), Vendor, reine SVGs.
- **Querschnitt (Ebene 3, `docs/system/`):** End-to-End Flows, Matrizen (Tenant, Admin, UI), Runbooks. Pflicht: Abschnitt "Betroffene Spiegel-Dateien".
- **Pflege:** Bei jeder Code-Änderung Spiegel mitziehen. Keine erfundenen Symbole/Endpoints. Broken-Links vermeiden (relative Pfade).
- **Neue Datei:** Spiegel sofort anlegen (Checkliste in `DOCUMENTATION_RULES.md` §9).
- **INDEX:** `docs/docs/INDEX.md` mitführen (Hälften-Tracking optional für Historie).
- **15_implementation_status.md:** Plan vs. Ist bei Abweichungen aktuell halten.

**Einstieg für neue Entwickler / Agents:**
1. `docs/README.md`
2. `docs/PROJECT_STANDARDS.md` (dieses) + `DOCUMENTATION_RULES.md`
3. `docs/13_coding_agent_brief.md` (Invarianten)
4. `docs/system/00_README.md` + `05_tenant_isolation.md`
5. Code + Spiegel unter `docs/docs/`

---

## Verweise

- Regeln: [`DOCUMENTATION_RULES.md`](./DOCUMENTATION_RULES.md)
- Invarianten & Bau: [`13_coding_agent_brief.md`](./13_coding_agent_brief.md)
- Tests: [`10_testing_strategy.md`](./10_testing_strategy.md), [`system/10_testing_landscape.md`](./system/10_testing_landscape.md)
- Review-Ergebnis: [`reviews/2026-06-05-project-review.md`](./reviews/2026-06-05-project-review.md)
- Aktueller Stand: [`15_implementation_status.md`](./15_implementation_status.md)
- Querschnitt: `system/00_README.md` … `12_integration_api.md`

---

## Changelog (dieses Dok)

- 2026-06-05: Initial (aus Review Phase 1/2): Prioritäten, Gate-Definition A/B, Doku-Pflicht-Index, Review-Referenz.

# 10 — Teststrategie

**Stand:** 2026-06-02 · **Status:** verbindlich für MVP

Grundsatz: Unit-Tests **ohne Netz** (OpenAI + Qdrant gemockt), deterministisch, schnell. Echte
Calls nur im manuellen Smoke/Demo. **Tenant-Isolation-Tests sind Pflicht, nicht optional.**

---

## 1. Testebenen
| Ebene | Was | Tooling |
|---|---|---|
| Unit | Chunking, Auth, Loader, Ingestion (gemockt), Agent (gemockt), **Isolation** | `pytest` + Mocks |
| Integration (optional) | echter Qdrant-Smoke pro Kunde | `pytest -m integration` |
| Manuell | Login, Kundenwahl, Upload, Frage, Löschen im Browser | Demo-Skript (§5) |

## 2. Was wird gemockt
- **OpenAI Embeddings:** deterministische Fake-Vektoren (dim 1536), keine HTTP-Calls.
- **OpenAI Chat/Agent:** Fake-LLM mit szenariogesteuerten Tool-Calls/Antworten.
- **Qdrant:** Fake-Store (In-Memory-Dict **pro Collection**) für Unit; echter Container nur `@integration`.
- `conftest.py`: Fixtures für Fake-Embeddings, Fake-LLM, Fake-Qdrant (mehrere Collections),
  temporäre SQLite-DB, geseedete Kunden/Nutzer/Zuordnungen.

## 3. Unit-Tests (Pflicht)

### `test_chunking.py`
- < Chunk-Größe → 1 Chunk; langer Text → mehrere mit Overlap; keine leeren; `chunk_index` ab 0;
  Whitespace normalisiert.

### `test_auth.py`
- `hash`/`verify` Roundtrip; falsches PW → Fehler; Hash ≠ Klartext; zwei Hashes unterscheiden sich.
- `get_current_user`: ohne Session → 401/Redirect; mit Session → Nutzer.
- Login: falsch → generische Meldung; richtig → Session; 1-Kunden-Nutzer → `customer_id` auto-gesetzt.

### `test_loaders.py`
- `.txt`/`.md` → Text; `.pdf` (Mini-Fixture) → Text; `.docx` (Mini-Fixture) → Text.
- **Leeres/kaputtes PDF → Fehler** (kein leerer Text durchgereicht).
- Nicht unterstützte Extension → Ablehnung.

### `test_ingestion.py`
- Erfolg (Fake-Embeddings/Store): 1 `documents`-Row (`customer_id`, `status=indexed`, korrektes
  `chunk_count`), n `chunks` (mit `customer_id`), n Points in `kb_{cid}`; `chunks.id==point_id`.
- Leerer/zu kurzer Text → Fehler, keine Rows/Points.
- Embedding-Fehler → kein `indexed`-Doc.
- `source_type` (`manual`/`file`) + Datei-Felder korrekt durchgereicht.

### `test_agent.py`
- A: Tool-Call → Treffer → finale Antwort mit **Quellen aus Retrieval**; `no_context=False`.
- B: keine Treffer über Schwelle → `NO_CONTEXT_TEXT`, leere Quellen, `no_context=True`.
- C: wiederholte Tool-Calls → Loop endet ≤ `MAX_TOOL_ROUNDS`.
- Citation-Dedup: gleicher `(document_id,chunk_index)` → eine Quelle, stabile Nummer.

### `test_tenant_isolation.py` — **PFLICHT**
1. Ingestion für `acme` und `globex` (Fake-Store) → Points landen in **getrennten** Collections.
2. `agent.run("globex", frage)` ruft Store nur mit `kb_globex` → **keine** `acme`-Treffer.
3. `GET /api/documents` als `globex`-Session listet **keine** `acme`-Dokumente.
4. Operation auf fremdem Kunden (`user∉customer`) → **403**.
5. `collection_name` lehnt ungültige/rohe Slugs ab.

## 4. Integrationstests (optional, `@integration`)
- Ingestion gegen echten Qdrant → Points abrufbar in `kb_{cid}`.
- Suche `globex` liefert nie `acme`-Punkte (reale Collections).
- Delete entfernt Punkte real.

## 5. Manuelles Smoke-/Demo-Skript
Voraussetzung: `.env` mit Key, `docker compose up`, Kunden/Nutzer/KB geseedet.
1. `/login` → Nutzer mit 2 Kunden (`acme`,`globex`) → landet auf `/`, Kunden-Dropdown sichtbar.
2. Kunde `acme` → PDF hochladen → erscheint in Liste (`[pdf]`, Chunks).
3. Frage zu PDF-Inhalt → belegte Antwort + Quellen `[1]…`.
4. Kunde auf `globex` wechseln → Liste leer / keine `acme`-Doks; gleiche Frage → No-Context.
5. Kaputtes PDF hochladen → `failed`-Status + Meldung, nichts durchsuchbar.
6. Dokument löschen → weg aus Liste + Suche. Abmelden → Redirect `/login`.
7. `GET /api/health` → `{"ok":true}`.

## 6. Abnahme-Mapping
| Gate / Anforderung | abgedeckt durch |
|---|---|
| Gate 1 (Upload+Antwort) | `test_loaders`+`test_ingestion`+`test_agent` + Smoke 2/3 |
| Gate 2 (Isolation) | `test_tenant_isolation` (Pflicht) + Smoke 4 |
| Gate 3 (Extraktion failed) | `test_loaders`+`test_ingestion` + Smoke 5 |
| Login/Schutz/403 | `test_auth`+`test_tenant_isolation` + Smoke 1 |
| No-Context | `test_agent` (B) + Smoke 4 |
| ohne Netz | gesamte Unit-Suite (NFR-3) |

## 7. Nicht im MVP
Last-/Performance-Tests, Playwright-E2E, Coverage-Gates.

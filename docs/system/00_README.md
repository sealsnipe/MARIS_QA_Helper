# System-Dokumentation — Einstieg

**Stand:** 2026-06-05 (Review-Update) 
**Ebene:** Querschnitt (dateiübergreifend)

---

## Drei Ebenen der Doku

| Ebene | Ort | Frage |
|---|---|---|
| **1 — Produkt & Planung** | [`docs/01_…`](../01_vision_and_scope.md) … [`docs/15`](../15_implementation_status.md) | Was soll das Produkt? Anforderungen, Architektur-Soll, API-Spec |
| **2 — Code-Spiegel** | [`docs/docs/`](../docs/INDEX.md) | Was macht Datei X? Symbole, Traces pro Quellfile |
| **3 — System / Querschnitt** | **`docs/system/`** (dieser Ordner) | Wie spielt alles zusammen? End-to-End, Mandant, Betrieb |

**Lesereihenfolge für neue Entwickler:**

1. [`docs/README.md`](../README.md) — Projektüberblick  
2. [`docs/PROJECT_STANDARDS.md`](../PROJECT_STANDARDS.md) (Prioritäten + Gate) + `DOCUMENTATION_RULES.md`  
3. Diese Datei + [`02_request_and_session_flow.md`](./02_request_and_session_flow.md)  
4. [`03_chat_pipeline.md`](./03_chat_pipeline.md) + [`04_ingestion_pipeline.md`](./04_ingestion_pipeline.md)  
5. [`05_tenant_isolation.md`](./05_tenant_isolation.md) — Pflicht-Invariante  
6. Bei Bedarf: Spiegel-Doku unter `docs/docs/backend/app/…` (siehe `docs/docs/INDEX.md`)

---

## Querschnitts-Index

| # | Dokument | Inhalt |
|---|---|---|
| 01 | [runtime_topology.md](./01_runtime_topology.md) | Dev (8090) vs Docker (8088) vs Prod-Overlays |
| 02 | [request_and_session_flow.md](./02_request_and_session_flow.md) | HTTP → Auth → Mandant → Handler |
| 03 | [chat_pipeline.md](./03_chat_pipeline.md) | Frage → Agent → Retrieval → Antwort |
| 04 | [ingestion_pipeline.md](./04_ingestion_pipeline.md) | Text/Upload → Chunks → SQLite + Qdrant |
| 05 | [tenant_isolation.md](./05_tenant_isolation.md) | Alle Enforcement-Punkte |
| 06 | [admin_flows.md](./06_admin_flows.md) | Kunden, User, KB, Prompts, Slug-Rename |
| 07 | [ui_map.md](./07_ui_map.md) | Seite → Template → JS → API |
| 08 | [data_model_sync.md](./08_data_model_sync.md) | SQLite ↔ Qdrant ↔ Uploads |
| 09 | [module_dependency_map.md](./09_module_dependency_map.md) | Modul-Schichten und Abhängigkeiten |
| 10 | [testing_landscape.md](./10_testing_landscape.md) | Tests vs Querschnitte |
| 11 | [operations_runbook.md](./11_operations_runbook.md) | Install, Dev, Deploy, Update |
| 12 | [integration_api.md](./12_integration_api.md) | Externe Agenten: POST /api/v1/ask |

**Ist-Stand Plan vs Code:** [`docs/15_implementation_status.md`](../15_implementation_status.md)

---

## Glossar (Kurz)

| Begriff | Bedeutung |
|---|---|
| `customer_id` | Mandanten-Slug (z. B. `bglu`) → Qdrant-Collection `kb_{id}` |
| `global` | Spezial-Mandant: durchsucht Global-KB + alle zugewiesenen Mandanten-KBs |
| Aktiver Kunde | `session["customer_id"]` — serverseitig, nie vom Client vertrauen |
| Soft-Delete | Dokument: `deleted_at` in SQLite + Qdrant-Points entfernt |

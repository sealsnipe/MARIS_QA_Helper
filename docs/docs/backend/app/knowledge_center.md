# `backend/app/knowledge_center.py`

**Quellpfad:** `backend/app/knowledge_center.py`

## Zweck und logischer Aufbau

Knowledge Center: Externer Content-Vorschlag (via Integration-API) → Review (adopt/reject) → optionale Übernahme in Ziel-KB (scoped ingest).

Quellen (`KnowledgeSource` via host_code), Contents (pending/adopted/rejected), Sichtbarkeit per User-Assignments (kein global).

Wird genutzt von Integration + Admin-Tools + Routes.

Lesereihenfolge: Status-Konstanten + Error → Validate/JSON-Helpers → to_dict → CRUD Sources → Visibility-Helpers → list/get Contents (user-scoped) → ingest (batch upsert pending) → adopt/reject (mit ingest_text) → list_adoptable.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.chunking.validate_ingest_text`
  - `app.customers` (GLOBAL, get, is_active, is_global, list_effective..., user_has_customer, validate_slug)
  - `app.ingestion` (IngestionError, ingest_text)
  - `app.models` (KnowledgeContent, KnowledgeSource, User)
  - SQLAlchemy (or_, select)
- **Wird genutzt von:** `app.integration_routes` (ingest), `app.routes` (Tools/Admin-KC Endpoints), `scripts/seed_knowledge_center_demo.py`
- **HTTP / UI:** /tools/knowledge-center* (Content + Sources), /api/tools/knowledge-center/*, /api/v1/knowledge-content
- **Daten:** knowledge_sources, knowledge_contents (mit status, suggested/adopted customer, external_id für Idempotenz)

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `CONTENT_STATUS_PENDING` | str | "pending" |
| `CONTENT_STATUS_ADOPTED` | str | "adopted" |
| `CONTENT_STATUS_REJECTED` | str | "rejected" |
| `CONTENT_STATUSES` | frozenset | Alle drei |

`KnowledgeCenterError(code, status_code=400, detail="")` — eigene Admin/Ingestion-Fehler.

## Funktionen und Klassen

### Source-Helpers
- `_validate_host_code`, `_validate_source_name`, `source_to_dict`
- `list_knowledge_sources`, `get_source_by_host_code`, `create_knowledge_source`, `update_knowledge_source`, `delete_knowledge_source` (mit has_contents-Check)

### Content-Helpers
- `_normalize_keywords`, `_keywords_to/from_json`, `content_to_dict`
- Visibility: `_visible_customer_ids`, `_content_visible_to_user`, `_content_visibility_filter`
- `list_knowledge_contents` (user + filter status/source/search + pagination + total), `get_knowledge_content_for_user` (404/403)

### Ingest / Review
- `_validate_content_item_fields` (title/summary/content/keywords/customer_id → suggested; ruft validate_ingest_text)
- `ingest_knowledge_contents(db, host_code, items)` → created/updated/skipped/errors (idempotent via external_id, nur pending updaten)
- `adopt_knowledge_content` (pending → ingest_text(scoped) → status=adopted + adopted_* + reviewed_*)
- `reject_knowledge_content`
- `list_adoptable_customers`

Fehler-Codes: invalid_*, unknown_*, forbidden*, source_*, empty_batch, not_found etc.

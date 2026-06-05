# `backend/app/tests/test_knowledge_center.py`

**Quellpfad:** `backend/app/tests/test_knowledge_center.py`

## Zweck und logischer Aufbau

Tests für KnowledgeCenter: Sources CRUD, visibility (user assigned vs suggested), ingest (batch), adopt (ingest + status), reject, list filters, errors (inactive, forbidden, dup source etc).

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `app.knowledge_center`, `app.ingestion`, `app.customers`, conftest (users with/without customers), db
- **Wird genutzt von:** pytest + integration tests
- **HTTP / UI:** Tools KC + Admin Sources
- **Daten:** knowledge_sources/contents, documents (adopt)

## (Optional) Tests

- Source create/update/delete (409 on contents).
- Ingest: pending, external_id update, suggested_customer validation.
- Visibility: user sieht nur assigned + none; adopt prüft user_has.
- Adopt: status change + document created (scoped ingest).
- Reject.
- Errors: invalid_host, source_inactive, forbidden_customer, not_found.

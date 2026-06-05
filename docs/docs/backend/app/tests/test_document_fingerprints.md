# `backend/app/tests/test_document_fingerprints.py`

**Quellpfad:** `backend/app/tests/test_document_fingerprints.py`

## Zweck und logischer Aufbau

Tests für Stufe-2 Duplikat (Qdrant Fingerprint): insert/search Fingerprints, similarity inspect in upload flow, warn/confirm.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `app.document_fingerprints`, `app.upload`, `app.qdrant_store` (InMemory), conftest fake
- **Wird genutzt von:** pytest + upload tests
- **HTTP / UI:** Inspect-Upload, Duplikat-Warnung bei ähnlichen
- **Daten:** Qdrant fingerprints (separate?); documents

## (Optional) Tests

- Fingerprint upsert bei ingest; search similar > threshold.
- inspect_similarity_payload: duplicate exact + similar list.
- Integration in upload: warn bei similar, allow_duplicate bypass.
- No false positive auf low score.

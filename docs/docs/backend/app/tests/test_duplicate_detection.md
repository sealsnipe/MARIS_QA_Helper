# `backend/app/tests/test_duplicate_detection.py`

**Quellpfad:** `backend/app/tests/test_duplicate_detection.py`

## Zweck und logischer Aufbau

End-to-End Duplikat-Tests (Stufe 1+2): exact hash, similar fingerprints, inspect payload, Upload-Error bei Duplikat (mit/ohne allow), UI-Warn.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `app.upload`, `app.duplicates`, `app.document_fingerprints`, `app.ingestion`, fake store/embed, client
- **Wird genutzt von:** pytest + upload_api tests
- **HTTP / UI:** POST /api/documents (multipart) mit Duplikat-Fällen
- **Daten:** documents, qdrant points (fingerprints)

## (Optional) Tests

- find_duplicate exact → 409 duplicate_document + payload.
- Similar (fingerprint) → inspect liefert similar[].
- allow_duplicate=True → akzeptiert.
- Nach Delete kein Duplikat mehr (soft).
- Content-Change → kein Duplikat.

# `backend/app/tests/test_document_merge.py`

**Quellpfad:** `backend/app/tests/test_document_merge.py`

## Zweck und logischer Aufbau

Tests für Merge-Preview (heuristic + LLM) und Apply: Block-Alignment, Compose, LLM-JSON-Parse, Confidence, final ingest via update.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `app.document_merge`, `app.ingestion` (update), fake embeddings/llm, db fixtures
- **Wird genutzt von:** pytest
- **HTTP / UI:** Admin Merge-Flow Endpoints
- **Daten:** documents (target), chunks/qdrant (via update)

## (Optional) Tests

- build_merge_preview: unchanged/modified/added/removed korrekt erkannt; stats.
- llm_suggest: JSON-Parse, Fallback, summary.
- compose mit client selections.
- apply: re-index mit merged, title override.
- Errors: empty, not_found, invalid_blocks, llm_disabled.
- Confidence + needs_llm_assist Logik.

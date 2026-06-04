# document_fingerprints.py

**Pfad:** `backend/app/document_fingerprints.py`

## Zweck

**Stufe 2 — ähnliche Dokumente:** pro indexiertem Dokument ein **Fingerprint-Vektor** in Qdrant; beim Inspect/Vor-Upload Similarity-Suche gegen bestehende Fingerprints desselben Mandanten.

Basis für späteren **Merge-Modus (Stufe 3)** — liefert `similar[].document_id` als Ziel-Dokument.

## Konstanten

- `FINGERPRINT_KIND = "document_fingerprint"`
- `FINGERPRINT_HEAD_CHARS = 4000`, `FINGERPRINT_TAIL_CHARS = 2000`
- Point-ID: `fp:{document_id}`

## API

### `build_fingerprint_text(title, normalized_text) -> str | None`

Titel + Volltext (gekürzt Head/Tail bei langen Docs) für Embedding.

### `upsert_document_fingerprint(...)`

Nach Chunk-Indexierung aufrufen (`ingestion._index_document_chunks`).

### `find_similar_documents(db, customer_id, text, ...) -> list[SimilarDocumentHit]`

Embedding der Upload-Probe → `vector_store.search_fingerprints` → Score ≥ `DUPLICATE_SIMILAR_MIN_SCORE` (Default 0.92).

Exakte Duplikate (Stufe 1) werden ausgeschlossen.

### `inspect_similarity_payload(db, customer_id, text)`

Kombiniert Stufe 1 + 2 für Inspect-Response: `(duplicate, similar[], content_sha256)`.

## Config

- `DUPLICATE_SIMILAR_MIN_SCORE` (Default 0.92)
- `DUPLICATE_SIMILAR_TOP_K` (Default 3)

## Stufe 3 Andockpunkt

Inspect liefert `similar: [{ document_id, title, score, match: "similar" }]`. Merge-Preview kann `target_document_id=similar[0].document_id` nutzen.

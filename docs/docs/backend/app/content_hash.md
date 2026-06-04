# content_hash.py

**Pfad:** `backend/app/content_hash.py`

## Zweck

Berechnet den **exakten Duplikat-Fingerprint** für indexierbaren Text: SHA256 über `normalize_text()` (wie Chunking/Ingest).

## API

### `content_sha256_from_text(text: str) -> str | None`

- Normalisiert Whitespace/Zeilenenden wie `chunking.normalize_text`.
- Gibt `None` zurück, wenn Text kürzer als `MIN_TEXT_LENGTH` (20 Zeichen).
- Sonst hex-encoded SHA256.

## Verwendung

- `ingestion.ingest_text` / `_index_document_chunks` — speichert Hash in `documents.content_sha256`.
- `ingestion.find_duplicate_document` — Lookup pro Mandant.
- `upload.inspect_upload` — liefert `duplicate` + `content_sha256` in der Inspect-Response.
- `upload.ingest_combined` — blockiert Upload bei Duplikat (`duplicate_document`, HTTP 409), außer `allow_duplicate=true`.

## Hinweis

Stufe 2 (ähnliche, nicht identische Dokumente) würde zusätzlich Vektor-Ähnlichkeit in Qdrant nutzen — nicht Teil dieses Moduls.

# 04 — Ingestion-Pipeline

**Stand:** 2026-06-03

---

## Pfade in die Pipeline

| Einstieg | Route | Kernfunktion |
|---|---|---|
| Text (Nutzer) | `POST /api/documents/text` | `ingest_text()` |
| Datei (Nutzer) | `POST /api/documents` | `ingest_combined()` → `ingest_text()` |
| Text (Admin global) | `POST /api/admin/documents` | `ingest_text(..., customer_id=global)` |
| Text (Admin pro Kunde) | `POST /api/admin/customers/{id}/documents` | `ingest_text(..., customer_id=id)` |
| **Bearbeiten (Admin)** | `GET/PUT /api/admin/documents/{id}` bzw. `…/customers/{cid}/documents/{id}` | `update_document_content` — Re-Index |

Alle mandant-scoped Nutzer-Routen: `customer_id` aus `get_current_customer`, **nie** aus Body.

---

## Ablauf `ingest_text`

```text
title + text validieren (chunking.validate_ingest_text)
  → chunk_text (CHUNK_SIZE/OVERLAP)
  → embeddings.embed_documents (OpenAI)
  → vector_store.ensure_collection + upsert (Qdrant)
  → SQLite: Document (inkl. `source_text`) + Chunk rows
  → bei Embedding-Fehler nach flush: `db.rollback()` — kein persistiertes Document
```

Bei Fehler nach Qdrant-Upsert: Rollback-Versuch `delete_document` auf Vektoren.

Spiegel: `ingestion.md`, `chunking.md`, `embeddings.md`, `qdrant_store.md`

---

## Ablauf Upload (`ingest_combined`)

1. Optional Prefix-Text + Datei-Bytes
2. Extension/Größe prüfen (`config.allowed_extensions`, `max_upload_bytes`)
3. Speichern: `./data/uploads/{customer_id}/{document_id}/{safe_filename}`
4. Loader (`txt`/`md`/`pdf`/`docx`) → Text
5. Kombinierter Text → `ingest_text` mit `storage_path`, `original_filename`

Extraktionsfehler: `Document` mit `status=failed` in SQLite, **keine** Qdrant-Points.

Spiegel: `upload.md`, `loaders/*.md`

---

## Löschen

`delete_document(db, customer_id, document_id)`:

- Qdrant: Points mit `document_id` filtern und löschen
- SQLite: `deleted_at` setzen (Soft-Delete)

Mandant-Check: `document.customer_id == customer_id`.

---

## Admin vs Nutzer-KB

- **Nutzer** (`/kb`): nur aktiver Mandant, read-only bei Scope `global`
- **Admin Wissen** (`/admin/knowledge`): Scope-Dropdown — global oder ein Mandant; **Bearbeiten** per Stift-Icon (inline Editor)
- **Global-KB** (`customer_id=global`): für alle Mandanten-Suchen mit sichtbar

---

## Ablauf Admin-Bearbeiten (`update_document_content`)

```text
GET: get_document_text → source_text oder Chunk-Rekonstruktion
PUT: validate → chunk → embed (zuerst) → Qdrant delete + Chunk-Rows löschen
  → neu upsert + source_text/title aktualisieren (gleiche document_id)
```

Datei-Ursprung: nach Speichern `source_type=manual`; `storage_path`/Originaldatei bleibt archiviert.

---

## Betroffene Spiegel-Dateien

`ingestion.md`, `upload.md`, `chunking.md`, `embeddings.md`, `qdrant_store.md`, `loaders/*.md`, `routes.md`, `templates/kb.md`, `templates/admin_knowledge.md`

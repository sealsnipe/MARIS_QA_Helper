# 04 — Ingestion-Pipeline

**Stand:** 2026-06-03

---

## Pfade in die Pipeline

| Einstieg | Route | Kernfunktion |
|---|---|---|
| Text (Nutzer) | `POST /api/documents/text` | `ingest_text()` |
| Inspect (Nutzer) | `POST /api/documents/inspect` | `inspect_upload()` |
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
  → SQLite: Document (inkl. `source_text`, optional `extraction_meta`) + Chunk rows
  → bei Embedding-Fehler nach flush: `db.rollback()` — kein persistiertes Document
```

Bei Fehler nach Qdrant-Upsert: Rollback-Versuch `delete_document` auf Vektoren.

Spiegel: `ingestion.md`, `chunking.md`, `embeddings.md`, `qdrant_store.md`

---

## Ablauf Upload (`ingest_combined`)

1. Optional Prefix-Text + Datei-Bytes
2. Extension/Größe prüfen (`config.allowed_extensions`, `max_upload_bytes`)
3. Speichern: `./data/uploads/{customer_id}/{document_id}/{safe_filename}`
4. **Inspect** (`inspect_document_path`) — Bildanzahl, `text_extractable`, `image_only`
5. Loader (`txt`/`md`/`pdf`/`docx`/Bild) → Text; reine Bilddateien → `extraction_failed` (erwartet)
6. **Alle erkannten Bilder** nach `./data/uploads/…/images/img_NNN.ext` (`save_embedded_images`)
7. Optional **Vision-OCR** nur für ausgewählte IDs (`process_images` + `transcribe_image_ids`)
8. Text zusammensetzen:
   - **DOCX:** inline via `compose_docx_with_vision` / Platzhalter
   - **PDF:** `append_pdf_image_blocks` (OCR + Platzhalter am Ende)
   - **Standalone Bild:** `merge_ocr_blocks` oder Platzhalter
9. Kombinierter Text → `ingest_text` mit `storage_path`, `original_filename`, `extraction_meta`

Extraktionsfehler ohne Bilder: Upload abgebrochen, Datei verworfen.  
Bild-only ohne Prefix und ohne Vision: `images_only_requires_vision`.

---

## Vision-OCR & Bildauswahl (UI)

```text
Datei wählen (Drag/Klick/Strg+V)
  → POST …/inspect → Thumbnails + IDs
  → Modal: Checkboxen pro Bild
  → „Ausgewählte transkribieren“ | „Ohne OCR einpflegen“ | Abbrechen
  → POST …/documents mit process_images + transcribe_image_ids (JSON)
  → run_vision_ocr(transcribe_ids=…)
  → Codex OAuth Streaming (VISION_MODEL, default gpt-5.4-mini)
```

Indexierter Text enthält `[BILD id="img_001"]…[/BILD]` oder `[BILD … status="nicht_verarbeitet"]`.  
Admin-Editor: Thumbnails klickbar (Lightbox), Label „· OCR“ / „· Vorschau“.

Env: `VISION_ENABLED`, `VISION_MODEL`, `VISION_MAX_IMAGES`, `LLM_AUTH_MODE=chatgpt_oauth`.

---

## Löschen

`delete_document(db, customer_id, document_id)`:

- Qdrant: Points mit `document_id` filtern und löschen
- SQLite: `deleted_at` setzen (Soft-Delete)

Mandant-Check: `document.customer_id == customer_id`.

---

## Admin vs Nutzer-KB

- **Nutzer** (`/kb`): nur aktiver Mandant, read-only bei Scope `global`
- **Admin Wissen** (`/admin/knowledge`): Scope-Dropdown — global oder ein Mandant; **Bearbeiten** per Stift-Icon (inline Editor + Bild-Thumbnails)
- **Global-KB** (`customer_id=global`): für alle Mandanten-Suchen mit sichtbar

---

## Ablauf Admin-Bearbeiten (`update_document_content`)

```text
GET: get_document_text → source_text oder Chunk-Rekonstruktion + images[]
PUT: validate → chunk → embed (zuerst) → Qdrant delete + Chunk-Rows löschen
  → neu upsert + source_text/title aktualisieren (gleiche document_id)
```

Datei-Ursprung: nach Speichern `source_type=manual`; `storage_path`/Originaldatei bleibt archiviert.

---

## Betroffene Spiegel-Dateien

`ingestion.md`, `upload.md`, `document_assets.md`, `loaders/image_inspect.md`, `loaders/vision_ocr.md`, `loaders/docx_content.md`, `llm.md`, `chunking.md`, `embeddings.md`, `qdrant_store.md`, `loaders/*.md`, `routes.md`, `static/app.md`, `templates/kb.md`, `templates/admin_knowledge.md`

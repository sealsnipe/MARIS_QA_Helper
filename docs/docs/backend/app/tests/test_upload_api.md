# `backend/app/tests/test_upload_api.py`

**Quellpfad:** `backend/app/tests/test_upload_api.py`

## Zweck und logischer Aufbau

Integrationstests für `POST /api/documents` (Multipart: optional `title`, `text`, `file`) — der Route-Handler ruft `ingest_combined` in `upload.py` auf. Abgedeckt werden reine Datei-Uploads, reiner Form-Text, Kombination, unsupported MIME/Endung und leerer Request.

Alle Tests nutzen denselben Mandanten-Setup (`bg-ludwigshafen`), Login und aktive Session vor dem Upload.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.tests.conftest`: `create_customer`, `create_user`, `login`
- **Wird genutzt von:** pytest
- **HTTP / UI:** `POST /api/documents`, `POST /api/session/customer`
- **Daten:** SQLite über Ingestion; Dateisystem `./data/uploads/{customer_id}/{document_id}/` bei Datei-Upload; InMemory-Qdrant (autouse)
- **Abgedecktes Modul:** `backend/app/upload.py` (`ingest_combined`), `backend/app/routes.py` (`api_upload_document`), `backend/app/main.py` (`UploadError`-Handler)

## Konstanten, Typen und Modulebene

Keine Modulebenen-Symbole in der Testdatei.

## Funktionen und Klassen

### `test_upload_txt_only(client, db_session)`

**Beschreibung:** Nur `files={"file": ...}` mit `.txt` — erfolgreiche Indexierung, `source_type` `txt`, Titel aus Dateistamm `notes`.

**Parameter / Rückgabe:** `client`, `db_session`.

**Ablauf / lokale Variablen:** `content` — Bytes mit genug Text; `payload["document"]` — `status == "indexed"`, `chunk_count >= 1`.

**Aufrufer / Aufgerufene:** `ingest_combined` mit Datei ohne `prefix_text`.

---

### `test_upload_text_only(client, db_session)`

**Beschreibung:** Nur `data` mit `title` und `text` (kein File) — `source_type` `manual`.

**Ablauf / lokale Variablen:** Form-Felder „Manueller Eintrag“ / langer Text; Assertion auf `title` und `source_type`.

**Aufrufer / Aufgerufene:** `ingest_combined` ohne `has_file`, `source_type` bleibt `manual`.

---

### `test_upload_combined_text_and_file(client, db_session)`

**Beschreibung:** Gleichzeitig `title`, `text` (Prefix) und `file` — kombinierter Ingest, Titel aus Form, `source_type` `txt` (Datei dominiert Typ wenn `file_text` gesetzt).

**Ablauf / lokale Variablen:** `file_content` + Einleitungstext; erwarteter Titel „Kombi-Dokument“.

**Aufrufer / Aufgerufene:** `_combine_text` in `upload.py`.

---

### `test_upload_unsupported_type(client, db_session)`

**Beschreibung:** `.exe` / `application/octet-stream` → HTTP 400, `error == "unsupported_file_type"`.

**Aufrufer / Aufgerufene:** `UploadError` → `upload_error_handler` in `main.py`.

---

### `test_upload_requires_content(client, db_session)`

**Beschreibung:** Leerer POST (weder Text noch Datei) → 400, `error == "empty_text"`.

**Aufrufer / Aufgerufene:** `ingest_combined` wirft `UploadError("empty_text")` wenn weder Prefix noch Datei.

## (Optional) Tests

- **Fixtures:** `client`, `db_session`; autouse `fake_embeddings`, `fake_vector_store`. Helfer: `create_customer`, `create_user`, `login`.
- **Abgedecktes Modul:** `backend/app/upload.py`, `backend/app/routes.py`, `backend/app/loaders`, `backend/app/ingestion.py`.

| Test | Intent |
|---|---|
| `test_upload_txt_only` | Datei-Upload `.txt` indexiert |
| `test_upload_text_only` | Reiner Formular-Text (`manual`) |
| `test_upload_combined_text_and_file` | Prefix-Text + Anhang |
| `test_upload_unsupported_type` | Abgelehnte Endung |
| `test_upload_requires_content` | Leerer Request abgelehnt |

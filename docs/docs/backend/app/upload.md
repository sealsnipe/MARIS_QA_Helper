# `backend/app/upload.py`

**Quellpfad:** `backend/app/upload.py`

## Zweck und logischer Aufbau

Kombiniert **Webformular-Text** (optionaler Prefix) und **Datei-Upload** zu einem Ingest-String, speichert Rohdateien unter `./data/uploads/{customer_id}/{document_id}/`, extrahiert Text über `load_document` und delegiert die Indexierung an `ingest_text`.

Fehler werden als `UploadError` mit maschinenlesbarem `code` geworfen; `main.py` mappt Codes auf HTTP-Status (400/413/422). Bei Extraktionsfehlern nach dem Speichern wird ein `Document` mit `status="failed"` in SQLite angelegt, bevor `UploadError("extraction_failed")` propagiert wird.

Lesereihenfolge: Exception `UploadError` → öffentliche Hilfsfunktion `sanitize_filename` → private Pfad-/Text-Helfer → öffentliche API `ingest_combined`.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.chunking.normalize_text`
  - `app.config.get_settings` (`allowed_extensions`, `max_upload_bytes`)
  - `app.ingestion.IngestionError`, `ingest_text`
  - `app.loaders.LoaderError`, `load_document`, `source_type_for_extension`
  - `app.models.Document`, `utc_now_iso`
  - Standard: `re`, `uuid`, `pathlib.Path`, `sqlalchemy.orm.Session`
- **Wird genutzt von:**
  - `backend/app/routes.py` — `api_upload_document` (`POST /api/documents`), weitere Admin-Upload-Pfade
  - `backend/app/main.py` — `UploadError`-Exception-Handler
  - `backend/app/tests/test_upload_api.py`
- **HTTP / UI:** `POST /api/documents` (multipart: `title`, `text`, `file`)
- **Daten:** SQLite `Document`; Dateisystem `./data/uploads/`; Qdrant über `ingest_text`

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `UploadError` | Exception-Klasse | Fachlicher Upload-/Ingest-Fehler mit `code` und optionalem `detail`; Message = `code` |

## Funktionen und Klassen

### Klasse `UploadError`

**Beschreibung:** Exception für Upload-Pipeline; `super().__init__(code)` setzt die Exception-Message auf den Code-String.

#### `__init__(self, code: str, detail: str | None = None) -> None`

**Parameter / Rückgabe:** `code` — Fehlerkennung (`empty_text`, `unsupported_file_type`, …); `detail` optional. Setzt `self.code`, `self.detail`.

**Aufrufer / Aufgerufene:** Geworfen in `ingest_combined`; abgefangen in `routes.py`, behandelt in `main.upload_error_handler`.

---

### `sanitize_filename(name: str) -> str`

**Beschreibung:** Normalisiert einen Upload-Dateinamen auf den Basisnamen, ersetzt unerlaubte Zeichen, kürzt auf 200 Zeichen.

**Parameter / Rückgabe:** `name` — roher Dateiname. Rückgabe: bereinigter String; Fallback `"upload"` wenn leer.

**Ablauf / lokale Variablen:** `base` — `Path(name).name`; `cleaned` — Regex `[^\w.\- ]` → `_`, dann `strip()`.

**Aufrufer / Aufgerufene:** Von `ingest_combined` und `_resolve_title` genutzt.

---

### `_upload_root() -> Path`

**Beschreibung:** Fester relativer Speicherort für Upload-Artefakte.

**Parameter / Rückgabe:** Keine. Rückgabe: `Path("./data/uploads")`.

**Aufrufer / Aufgerufene:** `ingest_combined` baut `storage_dir = _upload_root() / customer_id / document_id`.

---

### `_combine_text(prefix_text: str, file_text: str) -> str`

**Beschreibung:** Fügt nicht-leere Textteile mit doppeltem Zeilenumbruch zusammen.

**Parameter / Rückgabe:** Zwei Strings. Rückgabe: kombinierter Text oder `""`.

**Ablauf / lokale Variablen:** `parts` — Liste gestrippter nicht-leerer Segmente aus `(prefix_text, file_text)`.

**Aufrufer / Aufgerufene:** Nur `ingest_combined`.

---

### `_resolve_title(title: str | None, filename: str | None) -> str`

**Beschreibung:** Ermittelt Dokumenttitel: expliziter Titel, sonst Dateistamm, sonst Default „Wissenseintrag“ (max. 200 Zeichen).

**Parameter / Rückgabe:** Optionales `title` und `filename`. Rückgabe: `str`.

**Ablauf / lokale Variablen:** `cleaned` — gestrippter Titel; `stem` — aus `sanitize_filename(filename)` falls nötig.

**Aufrufer / Aufgerufene:** `ingest_combined` (auch im Loader-Fehlerpfad für `failed`-Document).

---

### `ingest_combined(db, customer_id, *, title=None, prefix_text=None, filename=None, content=None, mime_type=None) -> Document`

**Beschreibung:** Zentrale Upload-Ingestion: validiert Inhalt, speichert optional Datei, kombiniert Texte, ruft `ingest_text` auf, gibt indexiertes `Document` zurück.

**Parameter / Rückgabe:**
- `db` — SQLAlchemy-Session
- `customer_id` — Mandanten-ID
- Keyword-only: `title`, `prefix_text`, `filename`, `content` (Bytes), `mime_type`
- Rückgabe: `Document` aus `IngestResult`

**Ablauf / lokale Variablen:**
- `settings` — Konfiguration für erlaubte Endungen und Maximalgröße
- `prefix` — gestrippter `prefix_text`
- `has_file` — `content is not None and filename`
- `document_id` — neue UUID
- `safe_name`, `stored_path`, `file_text`, `file_source_type` — Dateipfad-Logik
- Bei Datei: Extension-Check, Größenlimit, `storage_dir.mkdir`, `write_bytes`, `load_document`
- Bei `LoaderError`: `failed`-`Document` mit `status="failed"`, commit, dann `UploadError("extraction_failed")`
- `combined` — `_combine_text`; Länge von `normalize_text(combined)` muss ≥ 20 sein
- `doc_title`, `source_type` — `manual` wenn nur Prefix, sonst Dateityp wenn `file_text`
- `result` — `ingest_text(...)`; `IngestionError` mit `empty_text` → `UploadError("empty_text")`

**Aufrufer / Aufgerufene:** `routes.api_upload_document` und weitere Routen; ruft `get_settings`, `sanitize_filename`, `load_document`, `ingest_text`, `normalize_text` auf.

**Fehlercodes (`UploadError.code`):** `empty_text`, `unsupported_file_type`, `file_too_large`, `extraction_failed`, `inspection_failed`, `images_only_requires_vision`, `vision_failed`, `duplicate_document` (409).

Inspect liefert zusätzlich **`similar[]`** (Stufe 2): `{ document_id, title, created_at, score, match: "similar" }` — Warnung only, kein Upload-Block.

---

### `inspect_upload(db, customer_id, content, filename, *, prefix_text=None) -> dict`

**Beschreibung:** Pre-Upload-Inspect für PDF, DOCX, Bilder und Textdateien; liefert `images[]` mit `preview_data_url` sowie **Duplikat-Hinweis** (`duplicate: { document_id, title, created_at } | null`, `content_sha256`).

Optionaler Form-Parameter `text` (Prefix) fließt in die Hash-Prüfung ein.

---

### `parse_transcribe_image_ids(value) -> set[str]`

**Beschreibung:** Parst JSON-Array oder kommagetrennte Liste gültiger IDs (`img_\d{3}`).

---

### `ingest_combined(…, process_images=False, transcribe_image_ids_raw=None, allow_duplicate=False) -> Document`

**Erweiterungen (2026-06-03):**

- Speichert **alle** erkannten Bilder unter `images/` (`save_embedded_images`)
- Vision-OCR nur für IDs in `transcribe_image_ids` wenn gesetzt; sonst alle (Legacy)
- Setzt `extraction_meta` mit `transcribed` pro Bild
- Unterstützt standalone Bilddateien (`.png`, …) — OCR oder Prefix-Text erforderlich

**Erweiterungen (2026-06-04):**

- Speichert `content_sha256` (exakter Duplikat-Hash) über `ingest_text`
- Blockiert Upload bei identischem Inhalt im Mandanten (`duplicate_document`), außer `allow_duplicate=true`

**Aufrufer:** `routes.py` — `process_images`, `transcribe_image_ids`, `allow_duplicate` Form-Felder.

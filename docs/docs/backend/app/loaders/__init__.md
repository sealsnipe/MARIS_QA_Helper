# `backend/app/loaders/__init__.py`

**Quellpfad:** `backend/app/loaders/__init__.py`

## Zweck und logischer Aufbau

**Fassade** für Datei-Loader im Upload-Pfad. Das Modul re-exportiert `LoaderError` und bietet zwei öffentliche Funktionen: `load_document` (Dispatcher nach Dateiendung) und `source_type_for_extension` (Metadaten für Ingestion).

Lesereihenfolge: Imports der spezifischen Loader → `load_document` → `source_type_for_extension` → `__all__`.

Im Request-Fluss ruft `app.upload.ingest_combined` zuerst `load_document` auf, um hochgeladene Dateien in Plaintext zu überführen, und setzt `source_type` via `source_type_for_extension`.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `app.loaders.docx_loader.load_docx`, `app.loaders.pdf_loader.load_pdf`, `app.loaders.text_loaders.load_text_file`, `app.loaders.errors.LoaderError`, `pathlib.Path`
- **Wird genutzt von:** `backend/app/upload.py` (`LoaderError`, `load_document`, `source_type_for_extension`), `backend/app/tests/test_loaders.py`
- **HTTP / UI / CLI:** indirekt über Upload-Routen (`api_upload_document`, `api_admin_upload_document` in `routes.py`)
- **Daten:** liest Dateien vom lokalen `storage_path` nach Upload

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `LoaderError` | Re-Export | Aus `app.loaders.errors` — siehe `loaders/errors.md` |
| `load_docx`, `load_pdf`, `load_text_file` | Re-Export (intern) | Spezifische Loader, nicht in `__all__` |
| `__all__` | Liste | `["LoaderError", "load_document", "source_type_for_extension"]` |

## Funktionen und Klassen

### `load_document(path: Path, extension: str) -> str`

**Beschreibung:** Dispatcht nach Dateiendung zum passenden Loader und liefert extrahierten Plaintext.

**Parameter / Rückgabe:** `path` — Pfad zur gespeicherten Datei; `extension` — Endung mit oder ohne führenden Punkt (wird lowercased); Rückgabe nicht-leerer Text.

**Ablauf / lokale Variablen:** `ext` — normalisierte Endung; Routing: `.txt`/`.md` → `load_text_file`, `.pdf` → `load_pdf`, `.docx` → `load_docx`.

**Aufrufer / Aufgerufene:** Aufgerufen von `upload.py`, Tests; ruft Loader-Submodule; wirft `LoaderError("unsupported_file_type")` bei unbekannter Endung.

---

### `source_type_for_extension(extension: str) -> str`

**Beschreibung:** Mappt Dateiendung auf `Document.source_type` für die Ingestion-Metadaten.

**Parameter / Rückgabe:** `extension` — Endung; Rückgabe `txt`, `md`, `pdf`, `docx` oder Fallback `"file"`.

**Ablauf / lokale Variablen:** `ext` — lowercased, führender Punkt entfernt.

**Aufrufer / Aufgerufene:** Aufgerufen von `upload.py` vor `ingest_text`.

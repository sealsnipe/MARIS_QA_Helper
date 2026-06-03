# `backend/app/loaders/errors.py`

**Quellpfad:** `backend/app/loaders/errors.py`

## Zweck und logischer Aufbau

Minimale **Fehlerklasse für Datei-Loader**. Alle Loader (`text_loaders`, `pdf_loader`, `docx_loader`) und der Dispatcher in `loaders/__init__.py` werfen `LoaderError` mit maschinenlesbaren Codes in der Exception-Message (z. B. `"extraction_failed"`, `"unsupported_file_type"`).

Die Datei enthält keine weiteren Symbole — Fehlerbehandlung erfolgt in `upload.py` (Map zu `UploadError`) und `main.py` (`upload_error_handler`).

## Abhängigkeiten und Traces

- **Importiert / nutzt:** keine Projektimports
- **Wird genutzt von:** `backend/app/loaders/__init__.py`, `docx_loader.py`, `pdf_loader.py`, `text_loaders.py`, `backend/app/upload.py` (Import über `app.loaders`)
- **HTTP / UI / CLI:** `unsupported_file_type` → 400, `extraction_failed` → 422 (via `UploadError`-Mapping in `main.py`)
- **Daten:** keine

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `LoaderError` | Exception-Klasse | Basis-Exception für Loader-Fehler; Message = Fehlercode-String |

## Funktionen und Klassen

### `LoaderError`

**Beschreibung:** Leerer Subclass von `Exception`; Aufrufer setzen den Code als Message (z. B. `raise LoaderError("extraction_failed")`).

**Aufrufer / Aufgerufene:** Geworfen in allen Loader-Modulen und `load_document`; in `upload.py` zu `UploadError` weitergegeben.

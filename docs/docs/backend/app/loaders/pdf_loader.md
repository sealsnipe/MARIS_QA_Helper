# `backend/app/loaders/pdf_loader.py`

**Quellpfad:** `backend/app/loaders/pdf_loader.py`

## Zweck und logischer Aufbau

Extrahiert **Plaintext aus PDF-Dateien** für die Wissensdatenbank-Ingestion. Nutzt `pypdf.PdfReader`, iteriert Seiten und sammelt nicht-leeren `extract_text()`-Output.

Lesereihenfolge: Import `LoaderError` → `load_pdf`.

Wird über `app.loaders.load_document` bei Endung `.pdf` aufgerufen.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `pypdf.PdfReader`, `app.loaders.errors.LoaderError`, `pathlib.Path`
- **Wird genutzt von:** `backend/app/loaders/__init__.py` (`load_document`-Dispatcher)
- **HTTP / UI / CLI:** indirekt über Upload-API
- **Daten:** liest lokale PDF unter Upload-Storage-Pfad

## Konstanten, Typen und Modulebene

Keine Modul-Level-Konstanten oder Klassen.

## Funktionen und Klassen

### `load_pdf(path: Path) -> str`

**Beschreibung:** Liest alle PDF-Seiten, extrahiert Text und joiniert mit doppelten Zeilenumbrüchen.

**Parameter / Rückgabe:** `path` — Pfad zur PDF; Rückgabe nicht-leerer String.

**Ablauf / lokale Variablen:** `reader` — `PdfReader(str(path))`; `parts` — Liste nicht-leerer Seitentexte; `text` — `"\n\n".join(parts).strip()`.

**Aufrufer / Aufgerufene:** Aufgerufen von `loaders/__init__.py`; wirft `LoaderError("extraction_failed")` bei Exception oder leerem Ergebnis.

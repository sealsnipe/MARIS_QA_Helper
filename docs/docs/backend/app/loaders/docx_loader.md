# `backend/app/loaders/docx_loader.py`

**Quellpfad:** `backend/app/loaders/docx_loader.py`

## Zweck und logischer Aufbau

Extrahiert **Plaintext aus DOCX-Dateien** für die Wissensdatenbank-Ingestion. Nutzt `python-docx`, iteriert Absätze und joiniert nicht-leere Absatztexte mit doppelten Zeilenumbrüchen.

Lesereihenfolge: Import `LoaderError` → `load_docx`.

Wird ausschließlich über `app.loaders.load_document` aufgerufen, wenn die Upload-Endung `.docx` ist.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `docx.Document` (als `DocxDocument`), `app.loaders.errors.LoaderError`, `pathlib.Path`
- **Wird genutzt von:** `backend/app/loaders/__init__.py` (`load_document`-Dispatcher)
- **HTTP / UI / CLI:** indirekt über Upload-API
- **Daten:** liest lokale DOCX-Datei unter Upload-Storage-Pfad

## Konstanten, Typen und Modulebene

Keine Modul-Level-Konstanten oder Klassen.

## Funktionen und Klassen

### `load_docx(path: Path) -> str`

**Beschreibung:** Öffnet DOCX, sammelt Absatztexte und liefert zusammengefügten Text.

**Parameter / Rückgabe:** `path` — Pfad zur `.docx`-Datei; Rückgabe nicht-leerer String.

**Ablauf / lokale Variablen:** `document` — `DocxDocument(str(path))`; `parts` — Liste getrimmter Absatztexte (nur nicht-leere); `text` — `"\n\n".join(parts).strip()`.

**Aufrufer / Aufgerufene:** Aufgerufen von `loaders/__init__.py`; wirft `LoaderError("extraction_failed")` bei Exception oder leerem Ergebnis.

# `backend/app/loaders/text_loaders.py`

**Quellpfad:** `backend/app/loaders/text_loaders.py`

## Zweck und logischer Aufbau

Lädt **Plaintext aus `.txt`- und `.md`-Dateien** mit UTF-8, Fallback auf Latin-1 bei Dekodierungsfehlern.

Lesereihenfolge: Import `LoaderError` → `load_text_file`.

Wird über `app.loaders.load_document` für Endungen `.txt` und `.md` aufgerufen.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `app.loaders.errors.LoaderError`, `pathlib.Path`
- **Wird genutzt von:** `backend/app/loaders/__init__.py` (`load_document`-Dispatcher), `backend/app/tests/test_loaders.py`
- **HTTP / UI / CLI:** indirekt über Upload-API
- **Daten:** liest lokale Textdatei vom Upload-Storage-Pfad

## Konstanten, Typen und Modulebene

Keine Modul-Level-Konstanten oder Klassen.

## Funktionen und Klassen

### `load_text_file(path: Path) -> str`

**Beschreibung:** Liest Dateiinhalt als String mit Encoding-Fallback.

**Parameter / Rückgabe:** `path` — Pfad zur Textdatei; Rückgabe nicht-leerer String (nach `strip()`).

**Ablauf / lokale Variablen:** `text` — zuerst `path.read_text(encoding="utf-8")`; bei `UnicodeDecodeError` erneut mit `latin-1`.

**Aufrufer / Aufgerufene:** Aufgerufen von `loaders/__init__.py`; wirft `LoaderError("extraction_failed")` bei `OSError` oder leerem Inhalt.

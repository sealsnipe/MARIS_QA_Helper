# `backend/app/tests/test_loaders.py`

**Quellpfad:** `backend/app/tests/test_loaders.py`

## Zweck und logischer Aufbau

Unit-Tests für die zentrale Loader-Fassade `load_document` in `app.loaders`: erfolgreiches Einlesen von `.txt` und `.md`, Fehler bei leerem Text und bei nicht unterstützten Dateiendungen.

Die Tests schreiben temporäre Dateien unter `tmp_path` (pytest) und rufen `load_document` mit expliziter Endung auf — ohne HTTP, DB oder Qdrant. Die Konstante `FIXTURES` verweist auf ein lokales `fixtures`-Verzeichnis neben der Testdatei, wird in den aktuellen Tests jedoch nicht verwendet.

Lesereihenfolge: Imports → `FIXTURES` → vier Testfunktionen mit steigender Fehlerstrenge.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.loaders`: `LoaderError`, `load_document`
  - `pytest`, `pathlib.Path`
- **Wird genutzt von:** pytest
- **HTTP / UI:** keine
- **Daten:** temporäre Dateien unter `tmp_path`; optional `backend/app/tests/fixtures/` (Pfadkonstante, ungenutzt in Tests)
- **Abgedecktes Modul:** `backend/app/loaders/__init__.py` → delegiert an `text_loaders.load_text_file` für `.txt`/`.md`

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `FIXTURES` | `Path` | `Path(__file__).resolve().parent / "fixtures"` — Verzeichnis für statische Testdateien (derzeit in keinem Test referenziert) |

## Funktionen und Klassen

### `test_load_txt(tmp_path: Path) -> None`

**Beschreibung:** Schreibt UTF-8-Text in `note.txt` und prüft, dass `load_document` den Inhalt enthält.

**Parameter / Rückgabe:** `tmp_path` — pytest-Tempverzeichnis. Kein Rückgabewert.

**Ablauf / lokale Variablen:** `path` — Zieldatei; `text` — Rückgabe von `load_document(path, ".txt")`; Assertion `"Support-Wissen" in text`.

**Aufrufer / Aufgerufene:** `load_document` → `load_text_file` in `text_loaders.py`.

---

### `test_load_md(tmp_path: Path) -> None`

**Beschreibung:** Markdown-Datei mit Überschrift und Absatz wird korrekt extrahiert.

**Ablauf / lokale Variablen:** `path` — `guide.md`; Assertion `"Markdown Inhalt" in text`.

**Aufrufer / Aufgerufene:** `load_document(..., ".md")`.

---

### `test_empty_txt_raises(tmp_path: Path) -> None`

**Beschreibung:** Nur Whitespace/Newlines in `.txt` löst `LoaderError` aus (`load_text_file` wirft `extraction_failed` bei leerem `strip()`).

**Ablauf / lokale Variablen:** `path` mit `"   \n"`; `pytest.raises(LoaderError)`.

**Aufrufer / Aufgerufene:** `load_document` propagiert `LoaderError`.

---

### `test_unsupported_extension(tmp_path: Path) -> None`

**Beschreibung:** Endung `.png` ist in `load_document` nicht implementiert → `LoaderError("unsupported_file_type")`.

**Ablauf / lokale Variablen:** Binärdummy in `image.png`; `load_document(path, ".png")` innerhalb `raises`.

**Aufrufer / Aufgerufene:** `load_document` in `loaders/__init__.py` (letzter Zweig: `raise LoaderError("unsupported_file_type")`).

## (Optional) Tests

- **Fixtures:** keine expliziten Conftest-Fixtures; nur `tmp_path` (pytest built-in). Autouse `fake_embeddings` / `fake_vector_store` laufen mit, sind für diese Datei irrelevant.
- **Abgedecktes Modul:** `backend/app/loaders/__init__.py`, `backend/app/loaders/text_loaders.py`, `backend/app/loaders/errors.py`.

| Test | Intent |
|---|---|
| `test_load_txt` | `.txt` erfolgreich lesen |
| `test_load_md` | `.md` erfolgreich lesen |
| `test_empty_txt_raises` | Leerer/Whitespace-Text → `LoaderError` |
| `test_unsupported_extension` | Unbekannte Endung → `LoaderError` |

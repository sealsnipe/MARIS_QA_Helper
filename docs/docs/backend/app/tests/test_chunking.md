# `backend/app/tests/test_chunking.py`

**Quellpfad:** `backend/app/tests/test_chunking.py`

## Zweck und logischer Aufbau

Unit-Tests für **Textnormalisierung**, **Chunking** und **Validierung** vor der Ingestion. Alle Tests rufen Funktionen aus `app.chunking` direkt auf — ohne HTTP-Client und ohne Datenbank.

Lesereihenfolge: Imports der Chunking-Konstanten und -Funktionen → fünf fokussierte Assertions zu Randfällen und Chunk-Grenzen.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.chunking`: `CHUNK_OVERLAP`, `CHUNK_SIZE`, `chunk_text`, `normalize_text`, `validate_ingest_text`
  - `pytest` (für `raises` in Validierungstest)
- **Wird genutzt von:** pytest; indirekt abgedeckt durch `backend/app/ingestion.py` (nutzt dieselben Funktionen)
- **HTTP / UI:** keine
- **Daten:** keine

## Konstanten, Typen und Modulebene

Die getesteten Modulkonstanten stammen aus `app.chunking` (nicht in dieser Datei definiert):

| Name | Art | Beschreibung (im Test genutzt) |
|---|---|---|
| `CHUNK_SIZE` | Konstante (importiert) | Maximale Chunk-Länge; alle Chunks `len(chunk) <= CHUNK_SIZE` |
| `CHUNK_OVERLAP` | Konstante (importiert) | Overlap > 0 bei langen Texten |

## Funktionen und Klassen

### `test_normalize_collapses_whitespace()`

**Beschreibung:** `normalize_text` kollabiert Leerzeichen und normalisiert Zeilenumbrüche.

**Parameter / Rückgabe:** Keine.

**Ablauf / lokale Variablen:** Eingabe mit mehrfachen Spaces/Newlines → erwarteter String `"Hallo Welt\n\nTest"`.

**Aufrufer / Aufgerufene:** `normalize_text`.

---

### `test_short_text_single_chunk()`

**Beschreibung:** Kurzer Text ergibt genau einen Chunk identisch zum Input.

**Ablauf / lokale Variablen:** `text`, `chunks` — `len(chunks) == 1`.

---

### `test_long_text_multiple_chunks_with_overlap()`

**Beschreibung:** Langer Text wird in mehrere nicht-leere Chunks ≤ `CHUNK_SIZE` zerlegt; Overlap-Konstante positiv.

**Ablauf / lokale Variablen:** `paragraph` wiederholt 300×, verdoppelt mit `\n\n`; `chunks` — Länge > 1.

---

### `test_chunk_indices_start_at_zero_via_ingestion_shape()`

**Beschreibung:** Chunking liefert nicht-leere Liste; erster Chunk beginnt erwartungsgemäß (Indizierung 0 in Ingestion-Pipeline).

**Ablauf / lokale Variablen:** `text` aus 80× wiederholtem Satz; `chunks[0].startswith("Wichtiger")`.

---

### `test_validate_rejects_too_short_text()`

**Beschreibung:** `validate_ingest_text` wirft `ValueError` mit Match `empty_text` für zu kurzen Text.

**Ablauf / lokale Variablen:** `pytest.raises(ValueError, match="empty_text")` mit `"zu kurz"`.

**Aufrufer / Aufgerufene:** `validate_ingest_text`.

## (Optional) Tests

- **Fixtures:** keine expliziten Conftest-Fixtures (reine Unit-Tests; `db_session`/`client` nicht genutzt). Autouse KI-Mocks laufen mit, sind hier irrelevant.
- **Abgedecktes Modul:** `backend/app/chunking.py`.

| Test | Intent |
|---|---|
| `test_normalize_collapses_whitespace` | Whitespace-Normalisierung |
| `test_short_text_single_chunk` | Ein Chunk bei kurzem Text |
| `test_long_text_multiple_chunks_with_overlap` | Mehrere Chunks, Größenlimit, Overlap |
| `test_chunk_indices_start_at_zero_via_ingestion_shape` | Erster Chunk-Inhalt plausibel |
| `test_validate_rejects_too_short_text` | Zu kurzer Ingest-Text → `empty_text` |

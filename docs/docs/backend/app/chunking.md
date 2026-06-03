# `backend/app/chunking.py`

**Quellpfad:** `backend/app/chunking.py`

## Zweck und logischer Aufbau

Textnormalisierung und absatzbasiertes Chunking für die Wissensbasis-Ingestion. Rohtext wird bereinigt, in überlappende Stücke zerlegt (Default 3500 Zeichen, 400 Overlap) und vor dem Embedding validiert (Mindestlänge). Die Logik ist rein funktional ohne DB- oder Netzwerkzugriff.

Lesereihenfolge: Modul-Konstanten → `normalize_text` → private `_split_paragraphs` → `chunk_text` (Kernalgorithmus mit `flush_current` und Overlap-Merge) → `validate_ingest_text` für Ingestion-Gate.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** Standardbibliothek `re` (Regex für Whitespace/Absätze)
- **Wird genutzt von:**
  - `backend/app/ingestion.py` — `chunk_text`, `validate_ingest_text`
  - `backend/app/upload.py` — `normalize_text` (Datei-Extraktion)
  - `backend/app/tests/test_chunking.py`
- **HTTP / UI:** indirekt über Upload- und Ingestion-Routen
- **Daten:** keine — liefert String-Listen für Downstream-Embedding

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `CHUNK_SIZE` | Konstante (`3500`) | Max. Zeichen pro Chunk |
| `CHUNK_OVERLAP` | Konstante (`400`) | Überlappung zwischen aufeinanderfolgenden Chunks |
| `MIN_TEXT_LENGTH` | Konstante (`20`) | Mindestlänge für gültigen Ingest-Text |

## Funktionen und Klassen

### `normalize_text(text: str) -> str`

**Beschreibung:** Vereinheitlicht Zeilenumbrüche, Whitespace und mehrfache Leerzeilen.

**Parameter / Rückgabe:** Rohtext → getrimmter Normalform-String.

**Ablauf / lokale Variablen:** Mehrstufige `re.sub`-Kette auf `\r\n`, Tabs, Rand-Whitespace an Zeilen.

**Aufrufer / Aufgerufene:** Von `chunk_text`, `validate_ingest_text`, `upload.py`.

---

### `_split_paragraphs(text: str) -> list[str]`

**Beschreibung:** Teilt Text an doppelten Zeilenumbrüchen in Absätze.

**Parameter / Rückgabe:** Normalisierter Text → Liste nicht-leerer Absätze.

**Aufrufer / Aufgerufene:** Nur von `chunk_text`.

---

### `chunk_text(text: str, *, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP) -> list[str]`

**Beschreibung:** Zerlegt Text in chunks unter Beachtung von Absatzgrenzen, Hard-Splits langer Absätze und optionalem Tail-Overlap-Merge.

**Parameter / Rückgabe:** Text und optionale Größen → Liste von Chunk-Strings (leer wenn Input leer).

**Ablauf / lokale Variablen:**
- `normalized` — via `normalize_text`
- `paragraphs` — aus `_split_paragraphs` oder Fallback `[normalized]`
- `chunks`, `current` — Akkumulator für laufenden Chunk
- `flush_current()` — inner closure: schreibt `current` in `chunks`
- Lange Absätze: Fenster `[start:end]` mit `overlap`-Schritt
- `overlapped` — optionaler Merge: hängt Tail des vorherigen Chunks an den nächsten, wenn unter `chunk_size`

**Aufrufer / Aufgerufene:** Aufrufer: `ingestion.py`, Tests.

---

### `validate_ingest_text(text: str) -> str`

**Beschreibung:** Normalisiert Text und lehnt zu kurze Inhalte ab.

**Parameter / Rückgabe:** Rohtext → normalisierter String.

**Ablauf / lokale Variablen:** `normalized` — muss `len >= MIN_TEXT_LENGTH`, sonst `ValueError("empty_text")`.

**Aufrufer / Aufgerufene:** Aufrufer: `ingestion.py`.

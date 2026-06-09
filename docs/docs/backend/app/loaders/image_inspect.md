# `backend/app/loaders/image_inspect.py`

**Quellpfad:** `backend/app/loaders/image_inspect.py`

## Zweck und logischer Aufbau

Erkennt **eingebettete oder standalone Bilder** in Upload-Dateien (PDF, DOCX, PNG/JPG/…) vor der Indexierung. Liefert Metadaten für Inspect-API und Upload-Pipeline (`has_images`, `image_count`, `text_extractable`, `image_only`).

Lesereihenfolge: Konstanten → Dataclass `ImageInspectResult` → öffentliche Inspect-Funktionen → private `_inspect_*` Helfer.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `docx`, `pypdf`, `app.loaders.errors.LoaderError`
- **Wird genutzt von:** `upload.py` (`inspect_upload`, `ingest_combined`), `vision_ocr.py` (`MIN_IMAGE_BYTES`)
- **HTTP:** indirekt `POST …/documents/inspect`

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `MIN_IMAGE_BYTES` | int | Mindestgröße (1024 B) für *eingebettete* Bilder (PDF/DOCX) — filtert kleine Deko/Hintergründe. Wird in `_is_meaningful_image` und vor den embedded-Inspektoren angewendet. |
| `IMAGE_FILE_EXTENSIONS` | frozenset | Standalone-Bildformate: `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif` |
| `ImageInspectResult` | dataclass | Roh-Ergebnis der Inspektion (has_images, image_count, pages_with_images, text_extractable, ...) |

## Funktionen und Klassen

### `inspect_result_to_dict(result) -> dict`

Serialisiert für JSON inkl. abgeleitetem `image_only`.

### `inspect_document_bytes(content, extension) -> ImageInspectResult`

Router: standalone Bild → `_inspect_image_file`; PDF → `_inspect_pdf`; DOCX → `_inspect_docx`.

### `inspect_document_path(path, extension) -> ImageInspectResult`

Liest Datei und delegiert an `inspect_document_bytes`.

### `_inspect_image_file(content, extension) -> ImageInspectResult`

Für **standalone** (vom User explizit hochgeladene) Bilddateien: prüft nur ob PIL `open` + `verify()` erfolgreich ist. Kein MIN-Byte-Filter — jede valide Bilddatei zählt als Bild (auch <1 KB). Bei Fehler (nicht dekodierbar) → has_images=False.

Für eingebettete Bilder (in PDF/DOCX) gelten weiter MIN + `_is_meaningful_image` (strict/lenient heuristic mit Varianz + unique colors, um echte Inhalte von Hintergründen zu unterscheiden). pdfimages (poppler) wird für Metadaten/Extraktion in OCR-Pfad genutzt wo verfügbar.

### `_is_meaningful_image(data, *, strict=True) -> bool`

Heuristik für eingebettete Bilder: Größe, PIL open, low-var / wenige Farben → False. strict=True auf text-haltigen Seiten (vermeidet Wasserzeichen etc.), lenient für reine Bildseiten.

### `_inspect_pdf`, `_inspect_docx`

Per-page Text-Erkennung zur Wahl strict/lenient; zählen nur meaningful images; listen pages_with_images.

### Hilfsfunktionen für pdfimages (poppler-utils)

`_has_pdfimages`, `_extract_images_pdfimages` — für originale Embed-Qualität (besser als pypdf Resample) im Vision-OCR Pfad (genutzt von vision_ocr.py). Der tote Code in `_inspect_pdf` (Temp-PDF + _list) wurde entfernt; Inspektion nutzt nur noch pypdf + _is_meaningful_image. `_list...` ersatzlos gelöscht (ungenutzt).

## Abhängigkeiten und Traces (aktualisiert)

- **Importiert / nutzt:** `docx`, `pypdf`, `PIL`, `subprocess`+`tempfile` (pdfimages), `app.loaders.errors.LoaderError`
- **Wird genutzt von:** `upload.py` (inspect_upload, build meta), `vision_ocr.py` (save_embedded, run_vision_ocr, extract via pdfimages first)
- **HTTP / UI:** indirekt POST /documents/inspect (Admin KB Ingest), Einpflegen-Button lock während async inspect
- **Daten:** Upload blobs, temp files für pdfimages

## Betroffene Planungsdocs

[`05_api_specification.md`](../../../05_api_specification.md), [`system/04_ingestion_pipeline.md`](../../../system/04_ingestion_pipeline.md)

## Tests

Siehe `backend/app/tests/test_image_inspect.py` und `test_selective_vision.py` (Noise-Fixtures für embedded, expliziter Filter-Test für Mini-Solid embedded, Standalone <1KB akzeptiert).

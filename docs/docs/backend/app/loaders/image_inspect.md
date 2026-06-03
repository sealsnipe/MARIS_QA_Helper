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
| `MIN_IMAGE_BYTES` | int | Mindestgröße (500 B) — kleinere Blobs werden ignoriert |
| `IMAGE_FILE_EXTENSIONS` | frozenset | Standalone-Bildformate: `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif` |
| `ImageInspectResult` | dataclass | Roh-Ergebnis der Inspektion |

## Funktionen

### `inspect_result_to_dict(result) -> dict`

Serialisiert für JSON inkl. abgeleitetem `image_only`.

### `inspect_document_bytes(content, extension) -> ImageInspectResult`

Router: standalone Bild → `_inspect_image_file`; PDF → `_inspect_pdf`; DOCX → `_inspect_docx`.

### `inspect_document_path(path, extension) -> ImageInspectResult`

Liest Datei und delegiert an `inspect_document_bytes`.

## Betroffene Planungsdocs

[`05_api_specification.md`](../../../05_api_specification.md), [`system/04_ingestion_pipeline.md`](../../../system/04_ingestion_pipeline.md)

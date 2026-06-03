# `backend/app/document_assets.py`

**Quellpfad:** `backend/app/document_assets.py`

## Zweck und logischer Aufbau

Hilfsmodul für **extrahierte Dokument-Bilder**: speichern auf Disk, `[BILD]`-Formatierung, Inspect-Vorschau (Base64-Thumbnail), Auflösung von Bild-Pfaden für API-Auslieferung, `extraction_meta`-Payloads.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `PIL`, `app.models.Document`
- **Wird genutzt von:** `upload.py`, `vision_ocr.py`, `routes.py` (Bild-GET)
- **Daten:** `./data/uploads/…/images/`, JSON in `Document.extraction_meta`

## Symbole (Auszug)

| Name | Beschreibung |
|---|---|
| `SavedDocumentImage` | id, filename, page, mime_type, **transcribed** |
| `format_image_block` | `[BILD id="…"]\n…\n[/BILD]` |
| `format_image_placeholder` | `[BILD … status="nicht_verarbeitet"]` |
| `build_image_preview_data_url` | Thumbnail für Inspect-Modal |
| `image_payloads` | URLs für Admin-Editor |

## Siehe auch

[`upload.md`](./upload.md), [`routes.md`](./routes.md)

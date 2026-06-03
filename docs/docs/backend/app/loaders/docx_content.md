# `backend/app/loaders/docx_content.py`

**Quellpfad:** `backend/app/loaders/docx_content.py`

## Zweck und logischer Aufbau

Parst DOCX-Struktur in **Dokumentreihenfolge** (Absätze, Tabellenzellen) und setzt OCR-Text oder Platzhalter **inline** an Bildpositionen — nicht am Ende des Dokuments.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `python-docx`, `document_assets.format_image_block`
- **Wird genutzt von:** `docx_loader.py`, `vision_ocr.compose_docx_with_vision`
- **Tests:** `test_docx_content.py`

## Funktionen (Auszug)

| Funktion | Beschreibung |
|---|---|
| `extract_docx_images_ordered` | Bilder in Lesereihenfolge mit stabilen IDs `img_001` … |
| `compose_docx_text` | Fließtext + `[BILD]`-Blöcke inline |
| `build_docx_image_id_map` | Mapping `rId` → `img_NNN` |

## Siehe auch

[`loaders/docx_loader.md`](./docx_loader.md), [`loaders/vision_ocr.md`](./vision_ocr.md)

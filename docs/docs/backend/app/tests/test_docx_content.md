# `backend/app/tests/test_docx_content.py`

**Quellpfad:** `backend/app/tests/test_docx_content.py`

## Zweck und logischer Aufbau

Tests für DOCX-spezifische Content-Handler (interleaved Text + Image-Placeholders, Vision-Compose).

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `app.loaders.docx_content`, fixtures (mini docx with images), pytest tmp
- **Wird genutzt von:** loaders, upload (vision path), tests
- **Daten:** temp .docx

## (Optional) Tests

- compose_docx_text mit/ohne ocr_text_by_id: korrekte Reihenfolge + Platzhalter.
- Bild-Extraktion + Placeholder-IDs.
- Fallback ohne Vision.

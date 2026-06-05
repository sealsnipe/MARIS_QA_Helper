# `backend/app/templates/tools/bild_zu_text.html`

**Quellpfad:** `backend/app/templates/tools/bild_zu_text.html`

## Zweck und logischer Aufbau

Tool-Seite: Bilder per Paste/Drop/Select → Vision-OCR → Text-Output (copy). Scoped zu aktuellem Kunden (oder global).

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `layout.html` (extends + scripts block)
- **Wird genutzt von:** routes `/tools/bild-zu-text`
- **HTTP / UI:** GET /tools/bild-zu-text (user + scoped); `initImageToTextTool` in app.js; POST /api/tools/vision (oder inspect/transcribe)
- **Daten:** Kein persist; temporäre Uploads für Vision

## (Optional) HTML / JS / CSS — zusätzliche Hinweise

- **Template:** extends layout; paste-zone #image-paste-zone (dropzone), hidden file-input, #image-preview-list grid, transcribe/clear btns, #transcribe-output + #output-content, #tool-status.
- **app.js:** `APP_BOOT.page === "tools_bild_zu_text"` → `initImageToTextTool()`: paste/drop handlers, preview render, transcribe fetch (FormData images), output render + copy.
- Wichtige IDs: image-paste-zone, image-file-input, image-preview-list, transcribe-btn, transcribe-output, tool-status.

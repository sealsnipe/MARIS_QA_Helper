# `backend/app/templates/tools/knowledge_center_content.html`

**Quellpfad:** `backend/app/templates/tools/knowledge_center_content.html`

## Zweck und logischer Aufbau

Content Dashboard (Tools): Filter (status/source/search), Grid von Cards (Vorschläge), Adopt/Reject Buttons, Load more. Sichtbar für zugewiesene User (kein Admin-only).

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `layout.html`
- **Wird genutzt von:** routes `/tools/knowledge-center`
- **HTTP / UI:** GET /tools/knowledge-center; JS `initKnowledgeCenterContentPage`; /api/tools/knowledge-center/contents + adopt/reject
- **Daten:** knowledge_contents (user-visible), sources

## (Optional) HTML / JS / CSS — zusätzliche Hinweise

- **Template:** extends; toolbar mit #kc-status-filter, #kc-source-filter, #kc-search-input, refresh; #kc-list-status; #kc-content-grid, #kc-empty, load-more.
- **app.js:** `APP_BOOT.page === "tools_kc_content"` → `initKnowledgeCenterContentPage()`: load sources+contents, filter handlers, render grid (cards mit adopt/reject), pagination.
- Wichtige IDs: kc-*-filter, kc-content-grid, kc-load-more-*, kc-list-status.

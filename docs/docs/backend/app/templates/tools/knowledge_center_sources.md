# `backend/app/templates/tools/knowledge_center_sources.html`

**Quellpfad:** `backend/app/templates/tools/knowledge_center_sources.html`

## Zweck und logischer Aufbau

Admin-Seite: Sources für KC (Name + Host-Code Slug, aktiv). CRUD. Nur Admin (global scope).

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `layout.html`
- **Wird genutzt von:** routes `/tools/knowledge-center/sources` (admin)
- **HTTP / UI:** GET .../sources; `initKnowledgeCenterSourcesPage`; /api/tools/knowledge-center/sources*
- **Daten:** knowledge_sources

## (Optional) HTML / JS / CSS — zusätzliche Hinweise

- **Template:** extends; create form #kc-source-create-form (name, host-code pattern), status; table #kc-source-table + body, count, empty.
- **app.js:** `APP_BOOT.page === "tools_kc_sources"` → `initKnowledgeCenterSourcesPage()`: load/render, create/update/delete (toggle active), status.
- Wichtige IDs: kc-source-create-*, kc-source-table-body, kc-source-*-status.

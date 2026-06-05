# `backend/app/templates/admin_keys.html`

**Quellpfad:** `backend/app/templates/admin_keys.html`

## Zweck und logischer Aufbau

Admin-Seite für Secrets/Keys (Chat, Embed, Similarity, Integration, OAuth Device). Zeigt Tabelle (masked/effective), Edit-Formulare, Device-Flow Dialog.

Erweitert `layout.html` (Admin-Nav, global customer scope).

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `layout.html` (extends), `base.html` indirekt
- **Wird genutzt von:** routes `/admin/keys` (admin only)
- **HTTP / UI:** GET /admin/keys; JS `initKeysPage` (in `app.js`); API /api/admin/keys*
- **Daten:** app_secrets (via API)

## (Optional) HTML / JS / CSS — zusätzliche Hinweise

- **Template:** `extends "layout.html"`, block title/page_title/content. Panel + Table #keys-table, #keys-table-body, #keys-count, status live regions. Modal #oauth-dialog mit verify-url, user-code, check/cancel.
- **app.js:** `APP_BOOT.page === "admin_keys"` → `initKeysPage()`: fetch list, render table, handlers für set/clear + oauth start/poll (fetch device, open dialog, poll).
- Wichtige IDs: keys-table, oauth-*, keys-list-status.

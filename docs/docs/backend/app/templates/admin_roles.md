# `backend/app/templates/admin_roles.html`

**Quellpfad:** `backend/app/templates/admin_roles.html`

## Zweck und logischer Aufbau

Admin-Seite Rollen-CRUD: Create-Form (Name, is_admin, auto_add, multi-customer checkboxes), Liste (edit/delete), Status.

Global scope (kein customer dropdown).

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `layout.html`
- **Wird genutzt von:** routes `/admin/roles`
- **HTTP / UI:** GET /admin/roles; `initRolesPage` in app.js; /api/admin/roles + customers
- **Daten:** roles + role_customers (via API)

## (Optional) HTML / JS / CSS — zusätzliche Hinweise

- **Template:** extends layout, form #role-create-form mit #role-create-name, checkboxes admin/auto, #role-create-customers (dynamisch), submit, status. Table #role-table + #role-table-body, count, empty.
- **app.js:** `APP_BOOT.page === "admin_roles"` → `initRolesPage()`: load customers+roles, render checkboxes/table, create/edit/delete handlers (PATCH/DELETE).
- Wichtige IDs: role-create-*, role-table-body, role-*-status.

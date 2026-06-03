# `backend/app/tests/test_admin_users.py`

**Quellpfad:** `backend/app/tests/test_admin_users.py`

## Zweck und logischer Aufbau

Integrationstests für die **Admin-Benutzerverwaltung** (`/api/admin/users`) und eine Redirect-Regel für Admins von `/kb` nach `/admin/knowledge`. Abgedeckt werden Zugriffskontrolle, CRUD inklusive Soft-Delete-Verhalten und Verbot des Selbstlöschens.

Lesereihenfolge: Conftest-Import → drei Testfunktionen mit Mandanten-/User-Setup und HTTP-Aufrufen.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.tests.conftest`: `create_customer`, `create_user`, `login`
- **Wird genutzt von:** pytest
- **HTTP / UI:**
  - `GET/POST/PATCH/DELETE /api/admin/users`, `DELETE /api/admin/users/{user_id}`
  - `GET /kb` (Admin-Redirect)
- **Daten:** SQLite `Customer`, `User`, `UserCustomer`
- **Abgedecktes Modul:** `backend/app/routes.py` (Admin-User-Handler)

## Konstanten, Typen und Modulebene

Keine Modulebenen-Symbole außer Testfunktionen.

## Funktionen und Klassen

### `test_admin_users_api_requires_admin(client, db_session)`

**Beschreibung:** Nicht-Admin erhält 403 auf `GET /api/admin/users`.

**Parameter / Rückgabe:** `client`, `db_session`.

**Ablauf / lokale Variablen:** Mandant + normaler User, Login, Assertion 403.

**Aufrufer / Aufgerufene:** Admin-Users-Liste in `routes.py`.

---

### `test_admin_users_crud(client, db_session)`

**Beschreibung:** Admin legt Benutzer an, listet, aktualisiert Mandanten-Zuordnung, deaktiviert per DELETE; Selbstlöschung des eingeloggten Admins ist 403.

**Parameter / Rückgabe:** `client`, `db_session`.

**Ablauf / lokale Variablen:**
- `admin` — angelegter Admin-User (`admin.id` für Self-Delete)
- `create_response` — POST mit `anna@example.com`, `customer_ids: ["kkrr"]`
- `user_id` — aus JSON
- `emails` — Set aus Listen-Response
- `update_response` — PATCH mit beiden Mandanten-IDs
- `anna` — nach DELETE: `is_active is False` (Soft-Delete)
- `self_delete` — DELETE `admin.id` → 403

**Aufrufer / Aufgerufene:** Admin-User-CRUD in `routes.py`.

---

### `test_admin_kb_redirects_for_admin(client, db_session)`

**Beschreibung:** Eingeloggter Admin: `GET /kb` → 302 `/admin/knowledge`.

**Parameter / Rückgabe:** `client`, `db_session`.

**Aufrufer / Aufgerufene:** KB-Redirect-Logik in `routes.py`.

## (Optional) Tests

- **Fixtures:** `client`, `db_session`; autouse KI-Mocks. Helfer: `create_customer`, `create_user`, `login`.
- **Abgedecktes Modul:** `backend/app/routes.py`.

| Test | Intent |
|---|---|
| `test_admin_users_api_requires_admin` | 403 für Nicht-Admin |
| `test_admin_users_crud` | Anlegen, Listen, PATCH Mandanten, Soft-Delete, kein Self-Delete |
| `test_admin_kb_redirects_for_admin` | Admin `/kb` → `/admin/knowledge` |

# `backend/app/roles_admin.py`

**Quellpfad:** `backend/app/roles_admin.py`

## Zweck und logischer Aufbau

Rollen-Administration (Presets): Rollen mit is_admin-Flag + auto_add_new_customers + zugeordnete Customers (via RoleCustomer).

Wird von Admin-UI /api/admin/roles genutzt; bei Customer-Create auto-assign via `assign_new_customer_to_auto_roles`.

Trennt Rollen-Logik sauber von users_admin / customers.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.customers` (get, is_global, validate_slug)
  - `app.models` (Role, RoleCustomer, User, UserCustomer, UserRole)
  - SQLAlchemy delete/select
- **Wird genutzt von:** `app.routes` (Admin-Roles Endpoints + list in user lists), `app.customers.create_tenant_customer` (auto), `app.users_admin`
- **HTTP / UI:** /admin/roles, /api/admin/roles*
- **Daten:** roles, role_customers, user_roles

## Konstanten, Typen und Modulebene

`RoleAdminError(code, status=400, detail="")` — eigene Fehler (forbidden_customer, invalid_*, unknown_*, not_found etc.).

## Funktionen und Klassen

### Interne
- `_role_customer_ids(db, role_id)`
- `_validate_customer_ids(db, customer_ids)` (filter global, validate, exist-check → Error)
- `_validate_role_name`
- `_set_role_customers` (delete+insert)

### Öffentlich
- `role_to_dict(db, role)` (inkl. customer_ids)
- `list_admin_roles(db)`
- `merge_role_preset(db, role_ids)` → (is_admin_or, union customers)
- `set_user_roles(db, user_id, role_ids)` (löscht alte UserRole, setzt neue; auto UserCustomer via effective)
- `create_admin_role(...)` , `update_admin_role(...)` (name/customers/is_admin/auto; set customers)
- `delete_admin_role(db, role_id)` (mit UserRole-Check → 409 if assigned)
- `assign_new_customer_to_auto_roles(db, customer_id)` (für alle auto_add-Rollen + Admins)
- `get_user_role_ids`, `get_user_effective_permissions` (is_admin or any role.is_admin; union customers)

Wird in User-Create/Update für Rollenzuordnung genutzt.

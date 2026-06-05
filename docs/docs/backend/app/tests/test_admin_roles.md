# `backend/app/tests/test_admin_roles.py`

**Quellpfad:** `backend/app/tests/test_admin_roles.py`

## Zweck und logischer Aufbau

Tests für Rollen-Admin: CRUD Rollen (mit Customers + Flags), User-Rollen-Set (merge permissions), auto_assign bei neuem Customer, Delete mit assigned-Check, Presets.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `app.roles_admin`, `app.customers`, `app.users_admin`, conftest (create_user etc.), client, admin login
- **Wird genutzt von:** pytest
- **HTTP / UI:** /api/admin/roles*, User-Admin mit Rollen
- **Daten:** roles, role_customers, user_roles, user_customers

## (Optional) Tests

- Create/Update/Delete Role (is_admin, auto_add, customers); 409 on dup / delete-assigned.
- set_user_roles + effective is_admin + customer union.
- assign_new_customer_to_auto_roles (bei create_customer).
- Forbidden global in role-customers.
- Non-admin 403.
- list mit customers.

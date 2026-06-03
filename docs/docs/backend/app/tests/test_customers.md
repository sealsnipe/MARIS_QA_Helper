# `backend/app/tests/test_customers.py`

**Quellpfad:** `backend/app/tests/test_customers.py`

## Zweck und logischer Aufbau

Gemischte Tests für **Mandanten-Slugs**, **Qdrant-Collection-Namen**, **User-API** (`/api/customers`, `/api/session/customer`), **Tenant-Guards** und direktes Verhalten von `get_current_customer` bei manipulierter Session.

Struktur: reine Funktionstests für `validate_customer_slug` und `collection_name` → parametrisierter Negativtest → HTTP-Integration mit `client` → abschließend asyncio-Test mit `MagicMock`-Request.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.customers.collection_name`, `validate_customer_slug`
  - `app.tenant.ForbiddenCustomerError`, `get_current_customer`
  - `app.tests.conftest`: `create_customer`, `create_user`, `login`
  - `asyncio`, `unittest.mock.MagicMock`, `pytest.mark.parametrize`
- **Wird genutzt von:** pytest
- **HTTP / UI:** `GET /api/customers`, `POST /api/session/customer`, `GET /api/tenant-check`
- **Daten:** SQLite `Customer`, `User`, `UserCustomer`; Session-Key `customer_id`
- **Abgedecktes Modul:** `backend/app/customers.py`, `backend/app/tenant.py`, `backend/app/routes.py`

## Konstanten, Typen und Modulebene

Keine eigenen Konstanten; parametrisierte Fälle über pytest-Decorator auf `test_validate_customer_slug_rejects_invalid`.

## Funktionen und Klassen

### `test_validate_customer_slug_accepts_production_ids()`

**Beschreibung:** Gültige Produktions-Slugs werden akzeptiert.

**Ablauf / lokale Variablen:** Assertions für `bg-ludwigshafen`, `kkrr`, `foo_bar-1`.

**Aufrufer / Aufgerufene:** `validate_customer_slug` in `customers.py`.

---

### `test_validate_customer_slug_rejects_invalid(invalid_slug)`

**Beschreibung:** Ungültige Slugs werden abgelehnt (parametrisiert).

**Parameter / Rückgabe:** `invalid_slug` — je ein Wert aus `["BG Ludwigshafen", "../bad-slug", "bad/b", "bad b", ""]`.

**Aufrufer / Aufgerufene:** `validate_customer_slug` → `False`.

---

### `test_collection_name_builds_prefixed_slug()`

**Beschreibung:** `collection_name` mit `prefix="kb_"` erzeugt `kb_bg-ludwigshafen`.

---

### `test_collection_name_rejects_invalid_slug()`

**Beschreibung:** Ungültiger Slug in `collection_name` → `ValueError`.

---

### `test_list_customers_only_returns_assigned(client, db_session)`

**Beschreibung:** Eingeloggter User sieht zugewiesene Mandanten inkl. `global` zuerst; `active` initial `None`.

**Ablauf / lokale Variablen:** `body["customers"]` — IDs `{global, bg-ludwigshafen, kkrr}`; erstes Element `global`.

---

### `test_single_customer_user_gets_auto_selected_on_login(client, db_session)`

**Beschreibung:** User mit einem Mandanten: `active == "kkrr"` direkt nach Login.

---

### `test_customer_switch_sets_active_session(client, db_session)`

**Beschreibung:** `POST /api/session/customer` setzt aktiven Mandanten in API-Response und Folge-`GET /api/customers`.

---

### `test_forbidden_customer_when_not_assigned(client, db_session)`

**Beschreibung:** Wechsel zu nicht zugewiesenem Mandanten → 403, `error: "forbidden_customer"`.

---

### `test_unknown_customer_returns_404(client, db_session)`

**Beschreibung:** Unbekannte `customer_id` → 404, `error: "not_found"`.

---

### `test_tenant_scoped_route_requires_active_customer(client, db_session)`

**Beschreibung:** `/api/tenant-check` ohne aktiven Mandanten → 403; nach Switch → 200 mit `customer_id`.

**Ablauf / lokale Variablen:** `blocked`, `allowed` — vor/nach `POST /api/session/customer`.

---

### `test_tenant_scoped_route_rejects_foreign_customer_in_session(client, db_session)`

**Beschreibung:** Session enthält fremden `customer_id` → `ForbiddenCustomerError` bei `get_current_customer`.

**Ablauf / lokale Variablen:** `user` nur `kkrr`; `request.session = {"customer_id": "bg-ludwigshafen"}`; `asyncio.run(get_current_customer(...))`.

**Aufrufer / Aufgerufene:** `get_current_customer` in `tenant.py`.

## (Optional) Tests

- **Fixtures:** `client`, `db_session` (HTTP-Tests); keine DB in Slug-/Collection-Unit-Tests. Helfer: `create_customer`, `create_user`, `login`.
- **Abgedecktes Modul:** `backend/app/customers.py`, `backend/app/tenant.py`, `backend/app/routes.py`.

| Test | Intent |
|---|---|
| `test_validate_customer_slug_accepts_production_ids` | Gültige Slugs |
| `test_validate_customer_slug_rejects_invalid` | Ungültige Slugs (parametrisiert) |
| `test_collection_name_builds_prefixed_slug` | Qdrant-Collection-Name |
| `test_collection_name_rejects_invalid_slug` | ValueError bei bad slug |
| `test_list_customers_only_returns_assigned` | Liste + global zuerst |
| `test_single_customer_user_gets_auto_selected_on_login` | Auto-`active` bei einem Mandanten |
| `test_customer_switch_sets_active_session` | Session-Switch |
| `test_forbidden_customer_when_not_assigned` | 403 forbidden_customer |
| `test_unknown_customer_returns_404` | 404 not_found |
| `test_tenant_scoped_route_requires_active_customer` | Tenant-Route braucht active |
| `test_tenant_scoped_route_rejects_foreign_customer_in_session` | Session-Tampering → Exception |

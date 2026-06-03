# `backend/app/tests/test_global_customer.py`

**Quellpfad:** `backend/app/tests/test_global_customer.py`

## Zweck und logischer Aufbau

Spezifische Tests für den **Global-Mandanten** (`GLOBAL_CUSTOMER_ID` aus `app.customers`): Sortierung in der Kundenliste, Session-Wechsel und **read-only** Wissensbasis (Listing mit `read_only`, Schreib-Ingest blockiert).

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.customers.GLOBAL_CUSTOMER_ID`
  - `app.tests.conftest`: `create_customer`, `create_user`, `login`
- **Wird genutzt von:** pytest
- **HTTP / UI:** `GET /api/customers`, `POST /api/session/customer`, `GET /api/documents`, `POST /api/documents/text`
- **Daten:** SQLite `Customer` mit ID `global` (Konstante)
- **Abgedecktes Modul:** `backend/app/customers.py`, `backend/app/routes.py`, `backend/app/tenant.py`

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `GLOBAL_CUSTOMER_ID` | Import aus `app.customers` | Mandanten-ID für Global-KB (Wert im Code: `"global"`) |

## Funktionen und Klassen

### `test_global_customer_in_nav_list(client, db_session)`

**Beschreibung:** `global` steht an erster Stelle in `/api/customers`; zugewiesener Mandant ebenfalls enthalten.

**Parameter / Rückgabe:** `client`, `db_session`.

**Ablauf / lokale Variablen:** `ids[0] == GLOBAL_CUSTOMER_ID`; `"bg-ludwigshafen" in ids`.

---

### `test_global_customer_switch(client, db_session)`

**Beschreibung:** Wechsel auf Global-Mandant per Session-API erfolgreich (`active`).

**Ablauf / lokale Variablen:** `POST /api/session/customer` mit `customer_id: GLOBAL_CUSTOMER_ID` → 200, `active` gleich Konstante.

---

### `test_global_kb_is_read_only(client, db_session)`

**Beschreibung:** Dokumentenliste markiert Global als read-only; Text-Ingest liefert 403 `read_only_scope`.

**Ablauf / lokale Variablen:** Session auf Global; `body["read_only"] is True`, `body["customer_id"] == GLOBAL_CUSTOMER_ID`; `blocked` — POST text mit langem Test-Text → 403.

**Aufrufer / Aufgerufene:** Read-only-Guard in Routes/Ingestion für Global-Scope.

## (Optional) Tests

- **Fixtures:** `client`, `db_session`; autouse KI-Mocks. Helfer: `create_customer`, `create_user`, `login`.
- **Abgedecktes Modul:** `backend/app/customers.py`, `backend/app/routes.py`.

| Test | Intent |
|---|---|
| `test_global_customer_in_nav_list` | Global zuerst in Kundenliste |
| `test_global_customer_switch` | Session-Wechsel auf global |
| `test_global_kb_is_read_only` | KB read-only, Ingest verboten |

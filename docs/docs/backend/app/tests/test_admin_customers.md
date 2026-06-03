# `backend/app/tests/test_admin_customers.py`

**Quellpfad:** `backend/app/tests/test_admin_customers.py`

## Zweck und logischer Aufbau

Tests für **Admin-Mandantenverwaltung**: REST-CRUD unter `/api/admin/customers`, Schutz des globalen Mandanten, HTML-Zugriff `/admin/customers`, sowie eine **direkte Unit-/Integrationsprüfung** von `rename_tenant_customer` inklusive SQLite-Referenzen und Qdrant-Migration.

Die ersten Tests nutzen `TestClient` und Session-Login; `test_rename_tenant_customer_migrates_refs_and_qdrant` arbeitet ohne HTTP-Client direkt auf `db_session` und `fake_vector_store`.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.tests.conftest`: `create_customer`, `create_user`, `login`
  - In `test_rename_tenant_customer_migrates_refs_and_qdrant`: `app.customers.create_tenant_customer`, `rename_tenant_customer`; `app.models` (`Chunk`, `Customer`, `Document`, `SystemPrompt`, `UserCustomer`); `sqlalchemy.select`; `app.qdrant_store.get_vector_store`
- **Wird genutzt von:** pytest
- **HTTP / UI:**
  - `GET/POST/PATCH/DELETE /api/admin/customers`, `DELETE /api/admin/customers/global`
  - `GET /api/customers` (Sichtbarkeit nach Anlage)
  - `GET /admin/customers`
- **Daten:** SQLite (`Customer`, `Document`, `Chunk`, `SystemPrompt`, `UserCustomer`); In-Memory-Qdrant (`kb_oldk` / `kb_newk`)
- **Abgedecktes Modul:** `backend/app/routes.py`, `backend/app/customers.py`

## Konstanten, Typen und Modulebene

Keine Symbole auf Modulebene außer pytest-Testfunktionen.

## Funktionen und Klassen

### `test_admin_customers_api_requires_admin(client, db_session)`

**Beschreibung:** Nicht-Admin erhält 403 auf `GET /api/admin/customers`.

**Parameter / Rückgabe:** `client`, `db_session`; keine Rückgabe.

**Ablauf / lokale Variablen:** Standard-Setup `bg-ludwigshafen` + `sven@example.com`, Login, `response.status_code == 403`.

**Aufrufer / Aufgerufene:** Admin-Customers-API in `routes.py`.

---

### `test_admin_customers_crud(client, db_session)`

**Beschreibung:** Vollständiger Admin-CRUD-Zyklus für Mandant `kkrr` inkl. Sichtbarkeit in `/api/customers`.

**Parameter / Rückgabe:** `client`, `db_session`.

**Ablauf / lokale Variablen:** `create_response` (POST), `list_response`, `ids` (Set der IDs), `me_response` (normale Kundenliste), `update_response` (PATCH Name „KKRR“), `delete_response`, `ids_after` ohne `kkrr`.

**Aufrufer / Aufgerufene:** `/api/admin/customers`, `/api/admin/customers/kkrr`, `/api/customers`.

---

### `test_admin_cannot_delete_global_customer(client, db_session)`

**Beschreibung:** Löschen von `global` ist verboten (403).

**Parameter / Rückgabe:** `client`, `db_session`.

**Ablauf / lokale Variablen:** Nur Admin-User ohne explizite Mandanten-Zuordnung; `DELETE /api/admin/customers/global` → 403.

**Aufrufer / Aufgerufene:** Delete-Handler mit Global-Schutz in `routes.py` / `customers.py`.

---

### `test_admin_customers_page_redirects_for_non_admin(client, db_session)`

**Beschreibung:** Nicht-Admin: `GET /admin/customers` → 302 `/chat`.

**Parameter / Rückgabe:** `client`, `db_session`.

**Aufrufer / Aufgerufene:** HTML-Route `/admin/customers`.

---

### `test_rename_tenant_customer_migrates_refs_and_qdrant(db_session, fake_vector_store)`

**Beschreibung:** Umbenennung `oldk` → `newk` migriert DB-Referenzen, System-Prompt-Scope und Qdrant-Collection/Payload.

**Parameter / Rückgabe:** `db_session`; `fake_vector_store` — In-Memory-Store aus Conftest.

**Ablauf / lokale Variablen:**
- `c` — via `create_tenant_customer(db_session, "oldk", "Old Kunde")`
- `doc`, `ch` — Test-`Document`/`Chunk` mit `customer_id="oldk"`
- `p` — `SystemPrompt(scope="oldk", ...)`
- `vs` — `get_vector_store()`; `upsert("oldk", [("pt1", ...)])`
- `newc` — Ergebnis von `rename_tenant_customer(db_session, "oldk", "newk")`
- Assertions: kein `Customer` `oldk`, `Document.customer_id == "newk"`, Prompt unter Key `newk`, Collection `kb_newk` vorhanden, Payload `customer_id == "newk"`

**Aufrufer / Aufgerufene:** `rename_tenant_customer`, `create_tenant_customer` in `customers.py`; Qdrant über `qdrant_store`.

## (Optional) Tests

- **Fixtures:** `client`, `db_session`, `fake_vector_store` (nur Rename-Test); autouse KI-Mocks. Helfer: `create_customer`, `create_user`, `login`.
- **Abgedecktes Modul:** `backend/app/routes.py`, `backend/app/customers.py`, `backend/app/models.py`, `backend/app/qdrant_store.py`.

| Test | Intent |
|---|---|
| `test_admin_customers_api_requires_admin` | 403 für Nicht-Admin auf Customers-API |
| `test_admin_customers_crud` | POST/GET/PATCH/DELETE Mandant + User-API-Sichtbarkeit |
| `test_admin_cannot_delete_global_customer` | `global` nicht löschbar |
| `test_admin_customers_page_redirects_for_non_admin` | HTML-Seite nur für Admin |
| `test_rename_tenant_customer_migrates_refs_and_qdrant` | Rename migriert SQLite + Qdrant + Prompt |

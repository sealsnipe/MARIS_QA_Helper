# `backend/app/tests/test_admin.py`

**Quellpfad:** `backend/app/tests/test_admin.py`

## Zweck und logischer Aufbau

Integrationstests für **Admin-Zugriff** auf System-Prompt-API, **Admin-Dokument GET/PUT** und Admin-HTML-Seiten.

Lesereihenfolge: Import der Conftest-Helfer → vier unabhängige `test_*`-Funktionen, jeweils mit DB-Setup, Login und HTTP-Aufrufen über `TestClient`.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.tests.conftest`: `create_customer`, `create_user`, `login`
- **Wird genutzt von:** pytest (Discovery `test_admin.py`)
- **HTTP / UI:**
  - `GET/PUT /api/admin/customers/{customer_id}/documents/{document_id}`
  - `GET /admin`, `GET /admin/knowledge`, `GET /admin/prompts`, `GET /admin/users`
  - `POST /login` (über `login()`)
- **Daten:** SQLite-Test-DB (`Customer`, `User` über Conftest-Helfer)
- **Abgedecktes Modul:** Admin-Logik in `backend/app/routes.py` (Handler mit Admin-Dependency), Session/Auth in `backend/app/auth.py`

## Konstanten, Typen und Modulebene

Keine Modulebenen-Konstanten, Klassen oder Hilfsfunktionen — nur pytest-Testfunktionen.

## Funktionen und Klassen

### `test_admin_api_requires_admin(client, db_session)`

**Beschreibung:** Nicht-Admin erhält 403 auf die Admin-System-Prompt-API.

**Parameter / Rückgabe:** `client` — FastAPI `TestClient`; `db_session` — SQLAlchemy-Session. Kein Rückgabewert; Assertions per pytest.

**Ablauf / lokale Variablen:** Legt Mandant `bg-ludwigshafen` und Benutzer `sven@example.com` an, loggt ein, ruft `GET /api/admin/system-prompt` auf; erwartet Status 403.

**Aufrufer / Aufgerufene:** `create_customer`, `create_user`, `login`; HTTP gegen `routes`-Admin-Endpoints.

---

### `test_admin_can_read_and_write_prompt(client, db_session)`

**Beschreibung:** Admin kann System-Prompt lesen und mit globalem Scope (`customer_id: null`) aktualisieren.

**Parameter / Rückgabe:** Wie oben.

**Ablauf / lokale Variablen:** Admin `admin@example.com` mit `is_admin=True`; `get_response` (200), `put_response` mit JSON `content` „Du bist der Maris Support-Assistent.“; prüft, dass `"Maris"` in `put_response.json()["content"]` vorkommt.

**Aufrufer / Aufgerufene:** `PUT /api/admin/system-prompt`, `GET /api/admin/system-prompt`.

---

### `test_admin_root_redirects_to_customers(client, db_session)`

**Beschreibung:** `GET /admin` leitet Admins auf `/admin/customers` weiter (302).

**Parameter / Rückgabe:** Wie oben.

**Ablauf / lokale Variablen:** `response.headers["location"] == "/admin/customers"`.

**Aufrufer / Aufgerufene:** HTML-Route `/admin` in `routes.py`.

---

### `test_admin_subpages_require_admin(client, db_session)`

**Beschreibung:** Nicht-Admin wird von Admin-Unterseiten nach `/chat` umgeleitet.

**Parameter / Rückgabe:** Wie oben.

**Ablauf / lokale Variablen:** Schleife über `path` in `("/admin/knowledge", "/admin/prompts", "/admin/users")`; jeweils 302 und `location == "/chat"`.

**Aufrufer / Aufgerufene:** Admin-HTML-Routen in `routes.py`.

---

### `test_admin_can_get_and_update_document(client, db_session, fake_vector_store, fake_embeddings)`

**Beschreibung:** Admin kann Dokument-Inhalt per GET laden und per PUT aktualisieren (Re-Index); falscher Mandant → 404.

**Ablauf / lokale Variablen:** `ingest_text` legt Testdokument an; GET prüft `title`, `text`, `editable`; PUT ändert Titel; PUT unter falschem `customer_id` → 404.

**Aufrufer / Aufgerufene:** `GET/PUT /api/admin/customers/{cid}/documents/{id}`, `update_document_content` indirekt.

## (Optional) Tests

- **Fixtures:** `client`, `db_session` (aus `conftest.py`); implizit `_auto_mock_ai` / `fake_embeddings` / `fake_vector_store` (autouse). Helfer: `create_customer`, `create_user`, `login`.
- **Abgedecktes Modul:** `backend/app/routes.py` (Admin-API und -Seiten), indirekt `backend/app/auth.py`.

| Test | Intent |
|---|---|
| `test_admin_api_requires_admin` | 403 für Nicht-Admin auf System-Prompt-API |
| `test_admin_can_read_and_write_prompt` | Admin GET/PUT System-Prompt erfolgreich |
| `test_admin_root_redirects_to_customers` | `/admin` → `/admin/customers` |
| `test_admin_subpages_require_admin` | Nicht-Admin: Admin-HTML → `/chat` |
| `test_admin_can_get_and_update_document` | Admin GET/PUT Dokument, Mandanten-Scope, 404 bei falschem Kunden |

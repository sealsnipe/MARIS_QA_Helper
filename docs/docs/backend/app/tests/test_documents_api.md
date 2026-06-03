# `backend/app/tests/test_documents_api.py`

**Quellpfad:** `backend/app/tests/test_documents_api.py`

## Zweck und logischer Aufbau

Integrationstests für die **Dokumenten-HTTP-API** (`/api/documents`, `/api/documents/text`) unter aktivem Mandanten sowie eine Sichtbarkeitsprüfung der **Kundenliste** für einen Admin-ähnlichen User mit mehreren Produktions-Mandanten.

Die Tests stellen sicher, dass ingestierte Dokumente nur im aktiven Mandanten erscheinen und dass zugewiesene Produktions-IDs in `/api/customers` sichtbar sind.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.tests.conftest`: `create_customer`, `create_user`, `login`
- **Wird genutzt von:** pytest
- **HTTP / UI:**
  - `POST /api/documents/text`, `GET /api/documents`
  - `POST /api/session/customer`, `GET /api/customers`
- **Daten:** SQLite `Customer`, `Document` (über Ingestion-Route); Conftest-Mocks für Embeddings/Qdrant (autouse)
- **Abgedecktes Modul:** `backend/app/routes.py`, `backend/app/ingestion.py`

## Konstanten, Typen und Modulebene

Keine Modulebenen-Symbole außer Testfunktionen.

## Funktionen und Klassen

### `test_documents_text_endpoint_scoped_to_active_customer(client, db_session)`

**Beschreibung:** Text-Ingest und Listing sind an den aktiven Mandanten gebunden; nach Mandantenwechsel ist die Liste leer.

**Parameter / Rückgabe:** `client`, `db_session`.

**Ablauf / lokale Variablen:**
- Aktiver Mandant `bg-ludwigshafen`
- `response` — POST mit Titel „VPN Runbook“ und langem Support-Text
- `body["document"]["customer_id"] == "bg-ludwigshafen"`, `chunk_count >= 1`
- `listing` — ein Dokument
- Nach Switch zu `kkrr`: `GET /api/documents` → leere `documents`

**Aufrufer / Aufgerufene:** Dokumenten-Routen in `routes.py`, Ingestion-Pipeline.

---

### `test_production_customers_visible_for_admin(client, db_session)`

**Beschreibung:** User mit mehreren Mandanten-Zuordnungen sieht `global` und alle zugewiesenen Produktions-IDs in `/api/customers`.

**Parameter / Rückgabe:** `client`, `db_session`.

**Ablauf / lokale Variablen:** Vier Mandanten plus `global`; User `admin@example.com` (nicht `is_admin=True`, nur viele `customer_ids`); `ids` — exakt `{global, bg-ludwigshafen, bg-frankfurt, detmold-lippe, kkrr}`.

**Aufrufer / Aufgerufene:** `GET /api/customers` in `routes.py`.

## (Optional) Tests

- **Fixtures:** `client`, `db_session`; autouse `fake_embeddings`, `fake_vector_store`. Helfer: `create_customer`, `create_user`, `login`.
- **Abgedecktes Modul:** `backend/app/routes.py`, `backend/app/ingestion.py`, `backend/app/customers.py`.

| Test | Intent |
|---|---|
| `test_documents_text_endpoint_scoped_to_active_customer` | Ingest/List mandantenscharf |
| `test_production_customers_visible_for_admin` | Alle zugewiesenen Mandanten in Nav-API |

# `backend/app/tenant.py`

**Quellpfad:** `backend/app/tenant.py`

## Zweck und logischer Aufbau

Schlankes Modul für **Mandantenauflösung im Request-Kontext**. Es stellt FastAPI-Dependencies bereit, die aus der Starlette-Session den aktiven `customer_id`-Slug lesen, Berechtigungen prüfen und das zugehörige `Customer`-ORM-Objekt zurückgeben.

Zentrale Rolle in mandantengebundenen API-Routen: Endpoints, die `Depends(get_current_customer)` nutzen, schlagen fehl, wenn kein Kunde gewählt ist, der User keinen Zugriff hat oder der Kunde inaktiv/nicht existent ist. Ungültige Session-Einträge werden bereinigt (`request.session.pop("customer_id")`).

Lesereihenfolge: Imports → Exception-Klassen → async Dependency `get_current_customer`.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.auth.get_current_user`, `NotAuthenticatedError`
  - `app.customers.get_customer`, `is_customer_active`, `user_has_customer`
  - `app.db.get_db`
  - `app.models.Customer`, `User`
  - FastAPI `Depends`, `Request`; SQLAlchemy `Session`
- **Wird genutzt von:**
  - `backend/app/routes.py` — viele `/api/*`-Handler mit `customer=Depends(get_current_customer)`
  - `backend/app/main.py` — Exception-Handler für `ForbiddenCustomerError`, `CustomerNotFoundError`
  - `backend/app/tests/test_customers.py` — direkter Test von `get_current_customer`
- **HTTP / UI / CLI:**
  - Session-Key: `customer_id` (gesetzt via `POST /api/session/customer` oder Login bei einem Kunden)
  - Fehler-JSON: `403 forbidden_customer`, `404 not_found` (über `main.py`)
- **Daten:** SQLite `Customer`, `UserCustomer`; Session-Cookie

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `ForbiddenCustomerError` | Exception-Klasse | Kein gültiger Mandant im Request-Kontext oder fehlende Berechtigung |
| `CustomerNotFoundError` | Exception-Klasse | Kunde existiert nicht (wird in `routes.py` bei expliziten Lookups geworfen, nicht in `get_current_customer`) |

## Funktionen und Klassen

### `ForbiddenCustomerError`

**Beschreibung:** Signalisiert, dass der Request keinen autorisierten aktiven Mandanten hat.

**Parameter / Rückgabe:** Keine Attribute; wird von Exception-Handlern in JSON/HTTP übersetzt.

**Aufrufer / Aufgerufene:** Geworfen in `get_current_customer`; Handler in `app.main.forbidden_customer_handler`.

---

### `CustomerNotFoundError`

**Beschreibung:** Signalisiert, dass eine angeforderte Kunden-ID nicht in der Datenbank existiert.

**Parameter / Rückgabe:** Leere Exception-Klasse.

**Aufrufer / Aufgerufene:** Importiert und geworfen in `routes.py` (z. B. Kundenwechsel, Admin-Operationen); Handler in `app.main.customer_not_found_handler`.

---

### `get_current_customer(request, user, db) -> Customer`

**Beschreibung:** FastAPI-Dependency: liefert den aus der Session gewählten, für den User zugänglichen und aktiven Mandanten.

**Parameter / Rückgabe:**
- `request: Request` — Zugriff auf `request.session`
- `user: User` — via `Depends(get_current_user)`
- `db: Session` — via `Depends(get_db)`
- **Rückgabe:** `Customer`-Instanz

**Ablauf / lokale Variablen:**
- `customer_id` — aus `request.session.get("customer_id")`; fehlt er → `ForbiddenCustomerError`
- Prüfung `user_has_customer(db, user.id, customer_id)`; bei Fehlschlag Session bereinigen → `ForbiddenCustomerError`
- `customer = get_customer(db, customer_id)`; `None` oder `not is_customer_active(customer)` → Session bereinigen → `ForbiddenCustomerError`

**Aufrufer / Aufgerufene:**
- Ruft auf: `user_has_customer`, `get_customer`, `is_customer_active`
- Wird injiziert in dokument-/chat-/upload-bezogene Routen in `routes.py`

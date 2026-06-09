# `backend/app/main.py`

**Quellpfad:** `backend/app/main.py`

## Zweck und logischer Aufbau

**FastAPI-Einstiegspunkt** der Anwendung: erstellt die `app`-Instanz, registriert Middleware, Router, Static Files, Startup-Hooks und zentralisierte Exception-Handler für domänenspezifische Fehler.

Lesereihenfolge: Modul-Level-Setup (`settings`, `static_dir`) → `lifespan` → `app`-Konfiguration → Exception-Handler (gruppiert nach Fehlertyp).

Beim Start (`lifespan`): `init_db()`, Seed des Global-Kunden und Default-System-Prompt. Requests laufen über `app.routes.router`; nicht authentifizierte Browser-Requests werden zu `/login` umgeleitet, API-Requests erhalten JSON 401.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `app.config.get_settings`, `app.db` (`init_db`, Modul `db_module` für `SessionLocal` im Lifespan), `app.routes.router`, `app.customers.ensure_global_customer`, `app.system_prompts.ensure_default_global_prompt`, diverse Domain-Exceptions (`AgentError`, `IngestionError`, `UploadError`, Auth-/Tenant-/Chat-Fehler), FastAPI/Starlette Middleware und Responses
- **Wird genutzt von:** Uvicorn/Gunicorn als `app.main:app`; `backend/app/tests/conftest.py` (`from app.main import app`)
- **HTTP / UI / CLI:** mount `/static`; Session-Cookie `session`; alle Routen aus `routes.py`; Redirect `/login` bei `NotAuthenticatedError` (non-API)
- **Daten:** SQLite via `init_db` beim Startup; keine direkten Qdrant-Zugriffe

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `settings` | Settings-Instanz | Via `get_settings()` beim Modulimport |
| `static_dir` | `Path` | `backend/app/static`, wird bei Bedarf angelegt (`mkdir(exist_ok=True)`) |
| `app` | `FastAPI` | Hauptanwendung mit `lifespan`, Middleware, Router |

## Funktionen und Klassen

### `lifespan(_app: FastAPI)`

**Beschreibung:** Async Context Manager für Startup/Shutdown; führt DB-Init und Seed-Operationen aus.

**Parameter / Rückgabe:** `_app` — FastAPI-Instanz (unbenutzt); yield trennt Startup von Shutdown.

**Ablauf / lokale Variablen:** `db` — kurzlebige `db_module.SessionLocal()`-Session für `ensure_global_customer` und `ensure_default_global_prompt` (Test-Override der Engine bleibt wirksam).

**Aufrufer / Aufgerufene:** An FastAPI übergeben; ruft `init_db`, `ensure_global_customer`, `ensure_default_global_prompt`.

---

### `not_authenticated_handler(request: Request, _exc: NotAuthenticatedError)`

**Beschreibung:** API-Pfade → JSON 401 `not_authenticated`; sonst Redirect 302 nach `/login`.

**Parameter / Rückgabe:** FastAPI Exception-Handler-Signatur; `JSONResponse` oder `RedirectResponse`.

**Aufrufer / Aufgerufene:** Registriert für `NotAuthenticatedError` aus `app.auth`.

---

### `chat_not_found_handler(_request: Request, _exc: ChatNotFoundError)`

**Beschreibung:** JSON 404 `not_found` für fehlende Chat-Sessions.

**Aufrufer / Aufgerufene:** Registriert für `ChatNotFoundError` aus `app.chats`.

---

### `chat_forbidden_handler(_request: Request, _exc: ChatForbiddenError)`

**Beschreibung:** JSON 403 `forbidden_customer` bei Chat-Zugriff auf falschen Mandanten.

**Aufrufer / Aufgerufene:** Registriert für `ChatForbiddenError`.

---

### `forbidden_handler(_request: Request, _exc: ForbiddenError)`

**Beschreibung:** JSON 403 `forbidden` für allgemeine Auth-Verweigerung.

**Aufrufer / Aufgerufene:** Registriert für `ForbiddenError` aus `app.auth`.

---

### `forbidden_customer_handler(_request: Request, _exc: ForbiddenCustomerError)`

**Beschreibung:** JSON 403 `forbidden_customer` bei Mandanten-Zugriffsfehler.

**Aufrufer / Aufgerufene:** Registriert für `ForbiddenCustomerError` aus `app.tenant`.

---

### `customer_not_found_handler(_request: Request, _exc: CustomerNotFoundError)`

**Beschreibung:** JSON 404 `not_found` wenn Kunde nicht existiert.

**Aufrufer / Aufgerufene:** Registriert für `CustomerNotFoundError`.

---

### `customer_admin_error_handler(_request: Request, exc: CustomerAdminError)`

**Beschreibung:** JSON-Fehlerantwort mit `exc.code`, optionalem `detail`, Status aus `exc.status_code`.

**Ablauf / lokale Variablen:** `body` — Dict mit mindestens `error`.

**Aufrufer / Aufgerufene:** Registriert für `CustomerAdminError` aus `app.customers`.

---

### `user_admin_error_handler(_request: Request, exc: UserAdminError)`

**Beschreibung:** Analog zu `customer_admin_error_handler` für Benutzer-Admin-Fehler.

**Aufrufer / Aufgerufene:** Registriert für `UserAdminError` aus `app.users_admin`.

---

### `ingestion_error_handler(_request: Request, exc: IngestionError)`

**Beschreibung:** Mappt `IngestionError.code` auf HTTP-Status und liefert JSON mit `error`/`detail`.

**Ablauf / lokale Variablen:** `status_by_code` — `empty_text`/`invalid_title` → 400, `not_found` → 404, `embedding_failed`/`vector_store_failed` → 502; Default 400.

**Aufrufer / Aufgerufene:** Registriert für `IngestionError` aus `app.ingestion`.

---

### `agent_error_handler(_request: Request, exc: AgentError)`

**Beschreibung:** JSON 502 mit `exc.code` und optionalem `detail` für Agent-/LLM-Fehler.

**Aufrufer / Aufgerufene:** Registriert für `AgentError` aus `app.agent`.

---

### `upload_error_handler(_request: Request, exc: UploadError)`

**Beschreibung:** Mappt Upload-Fehlercodes auf HTTP-Status (400, 413, 422).

**Ablauf / lokale Variablen:** `status_by_code` — u. a. `file_too_large` → 413, `extraction_failed` → 422.

**Aufrufer / Aufgerufene:** Registriert für `UploadError` aus `app.upload`.

---

### `unhandled_exception_handler(request: Request, exc: Exception)` (F4 update)

**Beschreibung:** Fängt alle nicht behandelten Exceptions. Für API-Routen: JSON mit `{"error":"internal_error","ref":"..."}` (kein `detail`/`str(exc)` Leak mehr). Kurze ref für Log-Korrelation.

**Ablauf:** `ref = uuid.uuid4().hex[:8]`; `logger.exception(..., ref, path)`; Response ohne sensitive Details.

**Aufrufer / Aufgerufene:** Registriert global. (grep in `app.js` auf "internal_error" ergab keine Stellen, die `detail` parsen — sichere Änderung; ref kann bei Bedarf in Status/Toasts gezeigt werden.)

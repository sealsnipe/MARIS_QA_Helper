# `backend/app/routes.py`

**Quellpfad:** `backend/app/routes.py`

## Zweck und logischer Aufbau

Zentrales **FastAPI-Routing**: HTML-Seiten (Jinja2), Session-Login, Mandantenwechsel, Chat-/KB-APIs und Admin-Endpunkte (Kunden, Benutzer, Wissensbasis, Systemprompts).

Lesereihenfolge: Imports → `router` / `templates` → Pydantic-Request-Models → Hilfsfunktionen (`_page_context`, …) → öffentliche HTML-Routen → JSON-APIs (Session, Dokumente, Chat) → Admin-APIs.

Typischer Request-Flow: Session-Auth via `get_current_user` → optional Mandant via `get_current_customer` → Fachlogik in `agent`, `ingestion`, `chats`, `system_prompts` usw. → JSON oder `TemplateResponse`.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.agent`, `app.chats`, `app.auth`, `app.customers`, `app.db`, `app.ingestion`, `app.models`, `app.tenant`, `app.system_prompts`, `app.retrieval`, `app.upload`, `app.users_admin`
  - FastAPI, Jinja2, Pydantic, SQLAlchemy
- **Wird genutzt von:**
  - `backend/app/main.py` (oder App-Factory) — Mount des `router`
  - `backend/app/static/app.js` — alle `/api/*`-Aufrufe
  - Templates unter `backend/app/templates/`
- **HTTP:** siehe Route-Handler unten
- **Daten:** SQLite (User, Customer, Document, Chat, SystemPrompt); Qdrant indirekt via Ingestion/Agent

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `router` | `APIRouter` | Sammelt alle Route-Handler |
| `templates` | `Jinja2Templates` | Verzeichnis `backend/app/templates` |
| `CustomerSwitchRequest` | Pydantic-Model | `customer_id: str` (min. 1 Zeichen) |
| `TextDocumentRequest` | Pydantic-Model | `title` (1–200), `text` (min. 1) |
| `ChatRequest` | Pydantic-Model | `message`, optional `top_k` (1–20), `chat_id` |
| `SystemPromptRequest` | Pydantic-Model | optional `customer_id`, `content` (min. 1) |
| `AdminCustomerCreateRequest` | Pydantic-Model | `customer_id`, `name` |
| `AdminCustomerUpdateRequest` | Pydantic-Model | optional `id`, `name` |
| `AdminUserCreateRequest` | Pydantic-Model | `email`, `password`, `customer_ids`, `is_admin` |
| `AdminUserUpdateRequest` | Pydantic-Model | optional Felder für PATCH |

## Funktionen und Klassen

### `_admin_page_redirect(user: User) -> RedirectResponse | None`

**Beschreibung:** Leitet Nicht-Admins von Admin-URLs nach `/chat` um; sonst `None`.

**Aufrufer / Aufgerufene:** Alle `admin_*_page`-Handler.

---

### `_page_context(request, user, db, *, active_page: str) -> dict`

**Beschreibung:** Gemeinsamer Jinja-Kontext für App-Seiten (Navigation, Mandanten, Admin-Liste).

**Ablauf / lokale Variablen:** `customers` (Nav), `active_customer_id` aus Session, `admin_customers`, `customer_labels`.

**Rückgabe:** Dict mit `user`, `customers`, `admin_customers`, `active_customer`, `is_admin`, `active_page`, `global_customer_id`, `customer_labels`.

---

### `_document_payload(document) -> dict`

**Beschreibung:** Serialisiert ein `Document`-ORM für JSON-APIs.

**Felder:** `id`, `customer_id`, `title`, `source_type`, `original_filename`, `mime_type`, `chunk_count`, `status`, `error_message`, Timestamps.

---

### `_documents_for_scope(db, user, customer) -> list[dict]`

**Beschreibung:** Dokumentliste je Mandant: Global-Modus aggregiert globale + zugewiesene Mandanten-KBs.

**Aufrufer / Aufgerufene:** `api_list_documents`; nutzt `list_documents_for_customers` oder `list_documents`.

---

### `_reject_global_write(customer: Customer) -> JSONResponse | None`

**Beschreibung:** Blockiert Schreibzugriffe im Global-Lese-Modus mit 403 `read_only_scope`.

**Aufrufer / Aufgerufene:** Dokument-POST/DELETE für Endnutzer-KB.

---

### `_admin_tenant_customer(db, customer_id: str) -> Customer`

**Beschreibung:** Löst Mandanten für Admin-KB-APIs auf; wirft `CustomerNotFoundError` bei global oder unbekannt.

---

## Route-Handler

### `health()` — `GET /api/health`

**Beschreibung:** Einfacher Liveness-Check.

**Rückgabe:** `{"ok": true}`

---

### `login_form(request, error=None)` — `GET /login`

**Beschreibung:** Login-Formular; bei bestehender Session Redirect nach `/chat`.

**Template:** `login.html`, Kontext `error`.

---

### `login(request, email, password, db)` — `POST /login`

**Beschreibung:** Authentifiziert per E-Mail/Passwort, setzt Session `user_id`; bei genau einem Mandanten auch `customer_id`. In-Memory Sliding-Window Rate-Limit (nachgeschärft Runde 2 / F5): Check vor `verify_password` (auch korrektes PW wird im Fenster geblockt); `>= 10` → sofort `rate_limited` (kein Argon2/DB-Lookup für gesperrte Keys); Pruning bei >1000 Einträgen (abgelaufene Keys per Comprehension entfernt); `_login_rate_key` Helper (request.client.host or "unknown", Reverse-Proxy-Semantik im Docstring dokumentiert — Limit wirkt faktisch per E-Mail, MVP-limitiert).

**Ablauf:** Rate-Check (vor PW) → ggf. rate redirect; sonst Fehler → `/login?error=1`; Erfolg → pop + Session → `/chat`.

---

### `logout(request)` — `POST /logout`

**Beschreibung:** Session leeren, Redirect `/login`.

---

### `root_redirect()` — `GET /`

**Beschreibung:** Redirect nach `/chat`.

---

### `chat_page(request, user, db)` — `GET /chat`

**Beschreibung:** Chat-UI für eingeloggte Benutzer.

**Template:** `chat.html`, `_page_context(..., active_page="chat")`.

---

### `kb_page(request, user, db)` — `GET /kb`

**Beschreibung:** Endnutzer-Wissensbasis; Admins werden nach `/admin/knowledge` umgeleitet.

**Template:** `kb.html` oder Redirect.

---

### `admin_page(user)` — `GET /admin`

**Beschreibung:** Admin-Einstieg → Redirect `/admin/customers` (nach Admin-Check).

---

### `admin_customers_page(request, user, db)` — `GET /admin/customers`

**Template:** `customers.html`, `active_page="customers"`.

---

### `admin_knowledge_page(request, user, db)` — `GET /admin/knowledge`

**Template:** `admin_knowledge.html`, `active_page="admin_knowledge"`.

---

### `admin_prompts_page(request, user, db)` — `GET /admin/prompts`

**Template:** `admin_prompts.html`, `active_page="admin_prompts"`.

---

### `admin_users_page(request, user, db)` — `GET /admin/users`

**Template:** `admin_users.html`, `active_page="admin_users"`.

---

### `api_list_customers(request, user, db)` — `GET /api/customers`

**Beschreibung:** Navigations-Mandantenliste für aktuellen Benutzer.

**Rückgabe:** `{ customers: [{id, name}], active: session customer_id }`.

---

### `api_set_customer(payload, request, user, db)` — `POST /api/session/customer`

**Beschreibung:** Setzt aktiven Mandanten in der Session nach Berechtigungsprüfung.

**Fehler:** `CustomerNotFoundError`, `ForbiddenCustomerError`.

**Rückgabe:** `{ active: customer_id }`.

---

### `api_me(request, user, db)` — `GET /api/me`

**Beschreibung:** Geschützte JSON-Route für Auth-Smoke-Tests.

**Rückgabe:** `user_id`, `email`, `is_admin`, `active_customer`.

---

### `api_tenant_check(customer=Depends(get_current_customer))` — `GET /api/tenant-check`

**Beschreibung:** Mandanten-scoped Test-Endpoint (M2).

**Rückgabe:** `customer_id`, `customer_name`.

---

### `api_list_documents(user, customer, db)` — `GET /api/documents`

**Beschreibung:** Dokumente für aktiven Mandanten; `read_only` im Global-Modus.

**Rückgabe:** `customer_id`, `read_only`, `documents`.

---

### `api_create_text_document(payload, customer, db)` — `POST /api/documents/text`

**Beschreibung:** Reiner Text-Ingest (`source_type="manual"`).

**Fehler:** Global-Schreibschutz; `IngestionError`.

**Rückgabe:** `{ document: … }`.

---

### `api_upload_document(customer, db, title, text, file)` — `POST /api/documents`

**Beschreibung:** Multipart-Upload (optional Titel, Prefix-Text, Datei) via `ingest_combined`.

**Fehler:** `UploadError`, Global-Schreibschutz.

---

### `api_chat(payload, user, customer, db)` — `POST /api/chat`

**Beschreibung:** Chat-Nachricht senden, Agent ausführen, Antwort persistieren.

**Ablauf:** Session laden/erzeugen → User-Message speichern → `run_agent` → Quellen via `filter_sources_by_answer_citations` → Assistant-Message speichern.

**Rückgabe:** `chat_id`, `chat_title`, `customer_id`, `answer`, `sources`, `no_context`.

**Fehler:** 400 `empty_message`; 404/403 Chat-Fehler; `AgentError`.

---

### `api_list_chats(user, customer, db)` — `GET /api/chats`

**Rückgabe:** `{ customer_id, chats: [session_to_dict…] }`.

---

### `api_create_chat(user, customer, db)` — `POST /api/chats`

**Beschreibung:** Leere Chat-Session anlegen.

**Rückgabe:** `{ chat: session_to_dict(session) }`.

---

### `api_get_chat(chat_id, user, customer, db)` — `GET /api/chats/{chat_id}`

**Rückgabe:** `{ chat, messages }` oder 404/403.

---

### `api_delete_chat(chat_id, user, customer, db)` — `DELETE /api/chats/{chat_id}`

**Rückgabe:** `{ deleted: true, id }` oder Fehler-JSON.

---

### `api_delete_document(document_id, customer, db)` — `DELETE /api/documents/{document_id}`

**Beschreibung:** Soft-Delete Dokument im Mandanten-Scope; Global-Schreibschutz.

---

### `api_get_system_prompt(customer_id=None, _admin, db)` — `GET /api/admin/system-prompt`

**Beschreibung:** Liest Prompt für Scope (`global` → `None`).

**Rückgabe:** `{ customer_id, content }`.

---

### `api_admin_list_customers(_admin, db)` — `GET /api/admin/customers`

**Rückgabe:** `{ customers: [customer_to_dict…] }`.

---

### `api_admin_create_customer(payload, _admin, db)` — `POST /api/admin/customers`

**Rückgabe:** `{ customer: … }` via `create_tenant_customer`.

---

### `api_admin_update_customer(customer_id, payload, request, _admin, db)` — `PATCH /api/admin/customers/{customer_id}`

**Beschreibung:** Umbenennen (Slug) und/oder Anzeigenamen ändern; Session `customer_id` wird bei Slug-Wechsel mitgezogen.

**Ablauf:** optional `rename_tenant_customer`, dann `update_tenant_customer`.

---

### `api_admin_delete_customer(customer_id, _admin, db)` — `DELETE /api/admin/customers/{customer_id}`

**Beschreibung:** Deaktiviert Mandant (`deactivate_tenant_customer`).

---

### `api_put_system_prompt(payload, admin, db)` — `PUT /api/admin/system-prompt`

**Beschreibung:** Speichert System-Prompt; `"global"` → Scope `None`.

**Rückgabe:** `customer_id`, `content`, `updated_at`.

---

### `api_admin_list_documents(_admin, db)` — `GET /api/admin/documents`

**Beschreibung:** Globale KB-Dokumente (`GLOBAL_CUSTOMER_ID`).

---

### `api_admin_upload_document(_admin, db, title, text, file)` — `POST /api/admin/documents`

**Beschreibung:** Ingest in globale KB.

---

### `api_admin_delete_document(document_id, _admin, db)` — `DELETE /api/admin/documents/{document_id}`

**Beschreibung:** Löscht Dokument aus globaler KB.

---

### `api_admin_get_document(document_id, _admin, db)` — `GET /api/admin/documents/{document_id}`

**Beschreibung:** Liefert `{ document, text, editable, from_file }` via `_admin_document_detail` für Admin-Editor.

---

### `api_admin_update_document(document_id, body, _admin, db)` — `PUT /api/admin/documents/{document_id}`

**Beschreibung:** Body `DocumentUpdateRequest` (`title`, `text`); ruft `update_document_content`, Re-Index; 404 bei `not_found`.

---

### `api_admin_list_customer_documents(customer_id, _admin, db)` — `GET /api/admin/customers/{customer_id}/documents`

**Beschreibung:** Dokumente eines Mandanten (Admin).

---

### `api_admin_upload_customer_document(customer_id, …)` — `POST /api/admin/customers/{customer_id}/documents`

**Beschreibung:** Ingest in Mandanten-KB via `_admin_tenant_customer`.

---

### `api_admin_delete_customer_document(customer_id, document_id, …)` — `DELETE /api/admin/customers/{customer_id}/documents/{document_id}`

**Beschreibung:** Löscht Mandanten-Dokument.

---

### `api_admin_get_customer_document(customer_id, document_id, …)` — `GET /api/admin/customers/{customer_id}/documents/{document_id}`

**Beschreibung:** Wie global GET, scoped auf Mandant.

---

### `api_admin_update_customer_document(customer_id, document_id, body, …)` — `PUT /api/admin/customers/{customer_id}/documents/{document_id}`

**Beschreibung:** Mandanten-scoped PUT für Admin-Bearbeitung.

---

### `api_admin_list_users(_admin, db)` — `GET /api/admin/users`

**Rückgabe:** `{ users, customers: assignable }`.

---

### `api_admin_create_user(payload, _admin, db)` — `POST /api/admin/users`

**Rückgabe:** `{ user: user_to_dict }`; wirft `UserAdminError`.

---

### `api_admin_update_user(user_id, payload, admin, db)` — `PATCH /api/admin/users/{user_id}`

**Beschreibung:** Benutzer bearbeiten (E-Mail, Passwort, Mandanten, Admin, aktiv).

---

### `api_admin_delete_user(user_id, admin, db)` — `DELETE /api/admin/users/{user_id}`

**Beschreibung:** Deaktiviert Benutzer (`deactivate_admin_user`).

**Rückgabe:** `{ deleted: true, id }`.

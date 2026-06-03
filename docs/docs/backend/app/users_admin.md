# `backend/app/users_admin.py`

**Quellpfad:** `backend/app/users_admin.py`

## Zweck und logischer Aufbau

Domänenlogik für **Admin-Benutzerverwaltung**: Benutzer auflisten, anlegen, aktualisieren (E-Mail, Passwort, Mandanten, Admin-/Aktiv-Flags) und deaktivieren. Mandanten-Zuordnungen laufen über `UserCustomer`; Validierung nutzt `customers`-Hilfen (Slug, Existenz, kein Global-Mandant als Zuweisung).

Fehler werden als `UserAdminError` mit `code`, `status_code` und optionalem `detail` geworfen; `main.py` liefert JSON `{"error": code}`.

Lesereihenfolge: `UserAdminError` → E-Mail-Normalisierung → Serialisierung `user_to_dict` → Listen/Validierungs-Helfer → CRUD `create_admin_user`, `update_admin_user`, `deactivate_admin_user` → `list_assignable_customers`.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.auth.hash_password`
  - `app.customers`: `get_customer`, `is_global_customer`, `list_tenant_customers`, `validate_customer_slug`
  - `app.models`: `User`, `UserCustomer`, `utc_now_iso`
  - SQLAlchemy: `delete`, `select`, `Session`
- **Wird genutzt von:**
  - `backend/app/routes.py` — `/api/admin/users` (GET/POST/PATCH/DELETE)
  - `backend/app/main.py` — `UserAdminError`-Handler
  - `backend/app/tests/test_admin_users.py` (indirekt)
- **HTTP / UI:**
  - `GET /api/admin/users` — `list_admin_users`, `list_assignable_customers`
  - `POST /api/admin/users` — `create_admin_user`
  - `PATCH /api/admin/users/{user_id}` — `update_admin_user`
  - `DELETE /api/admin/users/{user_id}` — `deactivate_admin_user`
- **Daten:** SQLite-Tabellen `users`, `user_customers`, `customers`

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `UserAdminError` | Exception-Klasse | Admin-API-Fehler mit `code`, `status_code` (Default 400), `detail`; Message = `code` |

## Funktionen und Klassen

### Klasse `UserAdminError`

#### `__init__(self, code: str, *, status_code: int = 400, detail: str = "") -> None`

**Beschreibung:** Speichert Fehlercode und HTTP-Status für den Exception-Handler.

**Parameter / Rückgabe:** `code` — z. B. `invalid_email`, `user_exists`; `status_code`, `detail` optional.

---

### `_normalize_email(email: str) -> str`

**Beschreibung:** Trimmt und lowercased E-Mail-Adressen.

**Aufrufer / Aufgerufene:** `create_admin_user`, `update_admin_user`.

---

### `user_to_dict(db: Session, user: User) -> dict`

**Beschreibung:** Serialisiert einen `User` inkl. zugeordneter `customer_ids` für Admin-API-Responses.

**Parameter / Rückgabe:** `db`, `user`. Rückgabe: Dict mit `id`, `email`, `is_admin`, `is_active`, `customer_ids`, `created_at`.

**Ablauf / lokale Variablen:** `customer_ids` — Scalar-Select auf `UserCustomer.customer_id`.

**Aufrufer / Aufgerufene:** `list_admin_users`, Routen nach create/update.

---

### `list_admin_users(db: Session) -> list[dict]`

**Beschreibung:** Alle Benutzer sortiert nach E-Mail, jeweils als Dict via `user_to_dict`.

**Ablauf / lokale Variablen:** `rows` — `select(User).order_by(User.email)`.

**Aufrufer / Aufgerufene:** `routes.api_admin_list_users`.

---

### `_validate_customer_ids(db: Session, customer_ids: list[str]) -> list[str]`

**Beschreibung:** Normalisiert und prüft Mandanten-Slugs; wirft bei Global-Mandant, ungültigem Slug oder unbekanntem Kunden.

**Parameter / Rückgabe:** Rohe ID-Liste. Rückgabe: deduplizierte, lowercased Slugs (leere Einträge übersprungen).

**Ablauf / lokale Variablen:** `slugs` — akkumulierte gültige IDs; `slug` — `raw.strip().lower()` pro Eintrag.

**Fehler:** `forbidden_customer` (403), `invalid_customer_id` (400), `unknown_customer` (404, `detail=slug`).

**Aufrufer / Aufgerufene:** `create_admin_user`, `update_admin_user`.

---

### `_set_memberships(db: Session, user_id: str, customer_ids: list[str]) -> None`

**Beschreibung:** Ersetzt alle `UserCustomer`-Zeilen eines Users (DELETE dann INSERT).

**Ablauf / lokale Variablen:** `delete(UserCustomer).where(user_id=...)`; Schleife `db.add(UserCustomer(...))`.

**Aufrufer / Aufgerufene:** Nach User-Anlage/Update.

---

### `create_admin_user(db, email, password, customer_ids, *, is_admin=False) -> User`

**Beschreibung:** Legt neuen Benutzer mit Passwort-Hash und Mandanten-Memberships an.

**Parameter / Rückgabe:** `email`, `password` (min. 8 Zeichen), `customer_ids`, optional `is_admin`. Rückgabe: persistierter `User`.

**Ablauf / lokale Variablen:** `normalized` — E-Mail; Prüfung `@` und Eindeutigkeit (`user_exists` 409); `slugs` — `_validate_customer_ids`; `row` — neuer `User` mit UUID-`id`.

**Aufrufer / Aufgerufene:** `hash_password`, `_validate_customer_ids`, `_set_memberships`; Route `api_admin_create_user`.

**Fehlercodes:** `invalid_email`, `invalid_password`, `user_exists`, plus Validierungsfehler aus `_validate_customer_ids`.

---

### `update_admin_user(db, user_id, *, actor_id, email=None, password=None, customer_ids=None, is_admin=None, is_active=None) -> User`

**Beschreibung:** Partielles Update; verhindert Selbst-Demotion und Selbst-Deaktivierung.

**Parameter / Rückgabe:** `actor_id` — ID des ausführenden Admins (Schutzregeln). Optionale Felder nur bei `is not None`. Rückgabe: aktualisierter `User`.

**Ablauf / lokale Variablen:** `row` — `db.get(User, user_id)`; bei E-Mail-Änderung Duplikat-Check; `is_admin`/`is_active` mit `user_id == actor_id`-Guards.

**Fehlercodes:** `not_found` (404), `invalid_email`, `user_exists`, `invalid_password`, `cannot_demote_self`, `cannot_deactivate_self` (403).

**Aufrufer / Aufgerufene:** `routes.api_admin_update_user`.

---

### `deactivate_admin_user(db: Session, user_id: str, *, actor_id: str) -> None`

**Beschreibung:** Setzt `is_active = 0` (Soft-Delete); kein Löschen der Zeile.

**Parameter / Rückgabe:** Kein Rückgabewert.

**Fehlercodes:** `cannot_deactivate_self` (403), `not_found` (404).

**Aufrufer / Aufgerufene:** `routes.api_admin_delete_user`.

---

### `list_assignable_customers(db: Session) -> list[dict]`

**Beschreibung:** Mandantenliste für Admin-UI-Zuweisung (`id`, `name`), ohne Global-Kunde — via `list_tenant_customers`.

**Rückgabe:** Liste von `{"id", "name"}`-Dicts.

**Aufrufer / Aufgerufene:** `routes.api_admin_list_users` (Feld `customers` in Response).

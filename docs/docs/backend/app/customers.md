# `backend/app/customers.py`

**Quellpfad:** `backend/app/customers.py`

## Zweck und logischer Aufbau

Mandantenverwaltung (Multi-Tenant): Slug-Validierung, Qdrant-Collection-Namen, User-Zuordnungen, Navigationslisten, Admin-CRUD und atomares Umbenennen (`rename_tenant_customer`) mit SQLite-, Qdrant- und Dateisystem-Migration. Der synthetische Mandant `global` kapselt mandantenübergreifende KB-Suche.

Lesereihenfolge: Regex/ Konstanten → `CustomerAdminError` → Validierungs- und Hilfsfunktionen → Listen/Abfragen → Admin-Mutationen (`create`, `update`, `rename`, `deactivate`) → Serialisierung und `ensure_global_customer`.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `logging`, `re`, `shutil`, `pathlib.Path`
  - `app.models.Customer`, `SystemPrompt`, `User`, `UserCustomer`, `utc_now_iso`
  - Lazy in `rename_tenant_customer`: `app.qdrant_store.VectorStore`, `get_vector_store`; `app.upload._upload_root`
  - `sqlalchemy` (`select`, `text`, `Session`)
- **Wird genutzt von:**
  - `backend/app/routes.py` — Nav, Admin-Kunden-API
  - `backend/app/main.py` — `ensure_global_customer`, `CustomerAdminError` Handler
  - `backend/app/tenant.py` — Zugriffsprüfung
  - `backend/app/retrieval.py`, `system_prompts.py`, `qdrant_store.py`
  - `backend/app/users_admin.py`, Seed-/Test-Module
- **HTTP / UI:** Admin-Kunden-Endpunkte und Mandanten-Auswahl in `routes.py`
- **Daten:** SQLite `customers`, `user_customers`, abhängige Tabellen; Qdrant `kb_{slug}`; FS `data/uploads/{slug}/`

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `CUSTOMER_SLUG_PATTERN` | `re.Pattern` | Erlaubt `[a-z0-9_-]+` für Slugs |
| `GLOBAL_CUSTOMER_ID` | Konstante (`"global"`) | ID des Global-Mandanten |
| `GLOBAL_CUSTOMER_NAME` | Konstante (`"Global"`) | Anzeigename Global |
| `CustomerAdminError` | Exception | Admin-Fehler mit `code`, `status_code`, `detail` |

## Funktionen und Klassen

### `CustomerAdminError`

**Beschreibung:** Strukturierter Fehler für Kunden-Admin-Operationen (HTTP-Status in Exception).

**Attribute:** `code`, `status_code` (Default 400), `detail`.

**Aufrufer / Aufgerufene:** Handler in `main.py`.

---

### `validate_customer_slug(customer_id: str) -> bool`

**Beschreibung:** Prüft Slug gegen `CUSTOMER_SLUG_PATTERN`.

---

### `is_customer_active(customer: Customer | None) -> bool`

**Beschreibung:** `True`, wenn Customer existiert und `active` gesetzt (Default-Attribut `1`).

---

### `collection_name(customer_id: str, prefix: str = "kb_") -> str`

**Beschreibung:** Bildet Qdrant-Collection-Namen; wirft `ValueError` bei ungültigem Slug.

**Aufrufer / Aufgerufene:** Aufrufer: `qdrant_store.py`, Tests.

---

### `is_global_customer(customer_id: str) -> bool`

**Beschreibung:** Vergleich mit `GLOBAL_CUSTOMER_ID`.

---

### `list_customers_for_user(db, user_id) -> list[Customer]`

**Beschreibung:** Aktive, zugewiesene Mandanten (ohne `global`), sortiert nach Name.

---

### `list_assigned_customer_ids(db, user_id) -> list[str]`

**Beschreibung:** IDs aus `list_customers_for_user`.

---

### `list_customers_for_nav(db, user_id) -> list[Customer]`

**Beschreibung:** Navigationsliste: optional `global` vorne, dann zugewiesene Mandanten.

**Ablauf / lokale Variablen:** `assigned`, `global_customer` — Global nur wenn User Mandanten hat und Global aktiv.

**Aufrufer / Aufgerufene:** Aufrufer: `routes.py` (Shell/Chat-UI).

---

### `list_all_customers(db, *, include_global=False) -> list[Customer]`

**Beschreibung:** Alle aktiven Customers; optional mit `global`.

---

### `list_tenant_customers(db, *, include_inactive=False) -> list[Customer]`

**Beschreibung:** Mandanten ohne `global`; optional inaktive.

---

### `list_production_customers(db) -> list[Customer]`

**Beschreibung:** Alias für aktive Tenant-Customers (Admin-Dropdowns).

---

### `user_has_customer(db, user_id, customer_id) -> bool`

**Beschreibung:** Zugriffsprüfung: Global erlaubt wenn User irgendeinen Mandanten hat; sonst Slug + aktive Zuordnung.

**Aufrufer / Aufgerufene:** Aufrufer: `tenant.py`.

---

### `create_tenant_customer(db, customer_id, name) -> Customer`

**Beschreibung:** Legt neuen Mandanten an und verknüpft alle aktiven Admins automatisch.

**Ablauf / lokale Variablen:** `slug`, `display_name`; wirft `CustomerAdminError` bei Global-Slug, ungültigem ID, leerem Namen, Duplikat.

---

### `update_tenant_customer(db, customer_id, name) -> Customer`

**Beschreibung:** Ändert Anzeigenamen eines Tenant-Mandanten.

---

### `rename_tenant_customer(db, old_customer_id, new_customer_id, *, vector_store=None) -> Customer`

**Beschreibung:** Zentrale Slug-Umbenennung mit Migration von Qdrant, SQLite-FKs und Upload-Verzeichnis.

**Parameter / Rückgabe:** Alte/neue Slugs; optional injizierbarer `VectorStore`.

**Ablauf / lokale Variablen (4 Stufen):**
1. `store.copy_collection(old_slug, new_slug)` — Vektordaten kopieren
2. SQLite: neue `Customer`-Zeile, `UPDATE` auf `user_customers`, `documents`, `chunks`, `chat_sessions`, `system_prompts`; alte Zeile löschen; `commit` oder Rollback + Qdrant-Cleanup
3. `store.delete_collection(old_slug)` — alte Collection entfernen (best effort)
4. `shutil.move` von `data/uploads/{old}` → `{new}` (best effort, Warning im Log)

**Aufrufer / Aufgerufene:** Aufrufer: Admin-API in `routes.py`, `test_admin_customers.py`.

---

### `deactivate_tenant_customer(db, customer_id) -> None`

**Beschreibung:** Setzt `active=0` (Soft-Delete); Global verboten.

---

### `customer_to_dict(customer: Customer) -> dict`

**Beschreibung:** API-Dict mit `id`, `name`, `active`, `created_at`.

---

### `ensure_global_customer(db: Session) -> Customer`

**Beschreibung:** Idempotent: legt Global-Mandanten an oder korrigiert Name/Aktiv-Flag.

**Aufrufer / Aufgerufene:** Aufrufer: `main.py` lifespan.

---

### `get_customer(db, customer_id) -> Customer | None`

**Beschreibung:** Lädt Customer by PK; `None` bei ungültigem Slug.

**Aufrufer / Aufgerufene:** Aufrufer: `tenant.py`, `users_admin.py`, intern.

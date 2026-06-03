# `scripts/seed_users.py`

**Quellpfad:** `scripts/seed_users.py`

## Zweck und logischer Aufbau

Idempotentes Anlegen von Benutzern (`User`), Passwort-Hashing und Verknüpfung mit Mandanten über `UserCustomer`. CLI: einzelner User (`--email`, `--password`, `--customers`) oder `--defaults` / leerer Aufruf für vordefinierte Produktions-Admins.

Reihenfolge: Hilfsfunktionen `_ensure_user`, `_ensure_membership` → öffentliche `seed_user` / `seed_defaults` → `main` mit argparse.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `app.auth.hash_password`; `app.customers.validate_customer_slug`; `app.db`, `app.models` (`User`, `Customer`, `UserCustomer`); `seed_data.ADMIN_EMAILS`, `DEFAULT_USERS`
- **Wird genutzt von:** `scripts/seed_setup.py`
- **Daten:** SQLite `users`, `user_customers`

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `ROOT` | `Path` | Repo-Root |

## Funktionen und Klassen

### `_ensure_user(db, email, password, *, is_admin=False) -> User`

**Beschreibung:** Findet oder erstellt einen User mit gehashtem Passwort; befördert ggf. zu Admin.

**Parameter / Rückgabe:** `normalized` — lowercased E-Mail; gibt `User` zurück.

**Ablauf / lokale Variablen:** Neuer User erhält `uuid.uuid4()` als `id`, `is_active=1`, `created_at=utc_now_iso()`.

**Aufrufer / Aufgerufene:** `hash_password`, `select(User)`.

---

### `_ensure_membership(db, user, customer_ids) -> None`

**Beschreibung:** Verknüpft User mit jedem Mandanten-Slug, falls Link fehlt.

**Ablauf:** `validate_customer_slug`; `db.get(Customer, …)` muss existieren; `UserCustomer` composite key `user_id` + `customer_id`.

---

### `seed_user(email, password, customers, *, is_admin=False) -> None`

**Beschreibung:** Transaktion: User + Memberships, dann `commit`.

**Aufrufer / Aufgerufene:** `_ensure_user`, `_ensure_membership`, `init_db`.

---

### `seed_defaults() -> None`

**Beschreibung:** Iteriert `DEFAULT_USERS` via `seed_user`; danach alle E-Mails in `ADMIN_EMAILS` auf `is_admin=1` setzen falls nötig.

---

### `parse_args() -> argparse.Namespace`

**Beschreibung:** CLI: `--email`, `--password`, `--customers`, `--defaults`.

---

### `main() -> None`

**Beschreibung:** Ohne vollständige Einzel-Args → `seed_defaults()`; sonst `seed_user` mit kommagetrennten Customer-Slugs.

# `scripts/seed_customers.py`

**Quellpfad:** `scripts/seed_customers.py`

## Zweck und logischer Aufbau

Idempotentes Anlegen und Aktualisieren von `Customer`-Zeilen in SQLite. Standardmenge kommt aus `seed_data.ALL_CUSTOMERS`. Wird direkt ausgeführt oder von `seed_setup.run_seed` aufgerufen.

Ablauf: `sys.path` → `backend` + `scripts` → `init_db()` → Schleife über Kunden → `commit` → Liste aller Kunden ausgeben.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `app.db.SessionLocal`, `init_db`; `app.models.Customer`, `utc_now_iso`; `seed_data.ALL_CUSTOMERS`
- **Wird genutzt von:** `scripts/seed_setup.py`; indirekt Setup/Install
- **Daten:** SQLite-Tabelle `customers` (über SQLAlchemy-Model `Customer`)

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `ROOT` | `Path` | Repo-Root (`parents[1]` von Skriptpfad) |

## Funktionen und Klassen

### `seed_customers(customers: tuple[tuple[str, str], ...] = ALL_CUSTOMERS) -> None`

**Beschreibung:** Legt fehlende Kunden an oder aktualisiert den Namen bei Abweichung; gibt abschließend alle Kunden sortiert aus.

**Parameter / Rückgabe:** `customers` — Iterable aus `(id, name)`; kein Rückgabewert.

**Ablauf / lokale Variablen:** `existing` — `db.get(Customer, customer_id)`; bei `None` neues `Customer` mit `active=1`, `created_at=utc_now_iso()`; sonst ggf. `existing.name` setzen. `rows` — alle Kunden nach `order_by(Customer.name)`.

**Aufrufer / Aufgerufene:** `init_db`, `SessionLocal`, `db.commit`; `__main__` ruft `seed_customers()` ohne Args.

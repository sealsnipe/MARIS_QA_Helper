# `backend/app/db.py`

**Quellpfad:** `backend/app/db.py`

## Zweck und logischer Aufbau

SQLAlchemy-Infrastruktur: Engine-Erzeugung (SQLite WAL), Session-Factory, deklarative `Base`-Klasse für ORM-Modelle, Schema-Initialisierung und leichte Laufzeit-Migrationen. Beim App-Start ruft `main.py` `init_db()` auf; FastAPI-Endpoints erhalten Sessions über `get_db`.

Lesereihenfolge: `Base` → private `_create_engine` (SQLite-PRAGMA) → Modul-Level `engine`/`SessionLocal` → `_migrate_schema` → `init_db` → Dependency `get_db`.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.config.get_settings`
  - `sqlalchemy` (`create_engine`, `event`, `inspect`, `text`, `DeclarativeBase`, `sessionmaker`, `Session`)
- **Wird genutzt von:**
  - `backend/app/models.py` — erbt `Base`
  - `backend/app/main.py` — `SessionLocal`, `init_db`
  - `backend/app/auth.py`, `routes.py`, `tenant.py` — `get_db`
  - `scripts/seed_*.py` — `SessionLocal`, `init_db`
  - `backend/app/tests/conftest.py` — Override von `get_db`
- **HTTP / UI:** jede Route mit `Depends(get_db)`
- **Daten:** SQLite (Default `./data/support_kb.sqlite3`); WAL-Modus; Tabellen via `Base.metadata.create_all`

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `Base` | Klasse (`DeclarativeBase`) | ORM-Basisklasse für alle Modelle |
| `engine` | SQLAlchemy Engine | Prozess-weite DB-Engine aus `DATABASE_URL` |
| `SessionLocal` | `sessionmaker` | Factory für DB-Sessions |

## Funktionen und Klassen

### `Base`

**Beschreibung:** Leere deklarative Basis; alle Modelle in `models.py` erben davon.

---

### `_create_engine(database_url: str)`

**Beschreibung:** Erzeugt Engine; bei SQLite `check_same_thread=False` und WAL-PRAGMA on connect.

**Ablauf / lokale Variablen:**
- `connect_args` — SQLite-spezifisch
- Listener `_set_sqlite_wal` — `PRAGMA journal_mode=WAL`

**Aufrufer / Aufgerufene:** Wird beim Modulimport für `engine` aufgerufen.

---

### `_migrate_schema(engine) -> None`

**Beschreibung:** Leichte additive Migrationen ohne Alembic (Spalten nachträglich).

**Ablauf / lokale Variablen:**
- Prüft `users.is_admin` — fehlt → `ALTER TABLE … ADD COLUMN`
- Prüft `customers.active` — fehlt → analog
- Prüft `documents.source_text` — fehlt → `ALTER TABLE documents ADD COLUMN source_text TEXT`

**Aufrufer / Aufgerufene:** Nur von `init_db`.

---

### `init_db() -> None`

**Beschreibung:** Registriert ORM-Tabellen, legt `data/`-Verzeichnis bei relativem SQLite-Pfad an, `create_all`, dann `_migrate_schema`.

**Ablauf / lokale Variablen:** Side-effect-Import `app.models` für Metadaten-Registrierung.

**Aufrufer / Aufgerufene:** Aufrufer: `main.py` lifespan, Seed-Skripte, Test-Fixtures.

---

### `get_db() -> Generator[Session, None, None]`

**Beschreibung:** FastAPI-Dependency: yield Session, schließt in `finally`.

**Aufrufer / Aufgerufene:** Aufrufer: FastAPI-Routen, überschreibbar in Tests via `dependency_overrides`.

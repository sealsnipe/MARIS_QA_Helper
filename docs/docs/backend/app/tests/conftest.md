# `backend/app/tests/conftest.py`

**Quellpfad:** `backend/app/tests/conftest.py`

## Zweck und logischer Aufbau

Zentrale **pytest-Konfiguration** für das Backend. Die Datei setzt Test-Umgebungsvariablen, bevor App-Module geladen werden, mockt Embeddings und Vektorstore, stellt isolierte SQLite-Sessions bereit und liefert Hilfsfunktionen zum Anlegen von Testdaten und Login.

Alle `test_*.py`-Dateien unter `backend/app/tests/` profitieren automatisch von den Fixtures (insbesondere `autouse`-Mocking der KI-Backends). Import-Reihenfolge ist kritisch: `OPENAI_API_KEY` und `SESSION_SECRET` werden per `os.environ.setdefault` gesetzt, **bevor** `from app.main import app` erfolgt.

Lesereihenfolge: Env-Setup → App-Imports → `FakeEmbeddings` → Fixtures (`fake_embeddings`, `fake_vector_store`, `_auto_mock_ai`, `db_session`, `client`) → Hilfsfunktionen (`create_customer`, `create_user`, `login`).

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.auth.hash_password`
  - `app.customers.validate_customer_slug`
  - `app.db.SessionLocal`, `get_db`, `init_db`
  - `app.embeddings.set_embeddings_backend`
  - `app.main.app`
  - `app.models.Customer`, `User`, `UserCustomer`, `utc_now_iso`
  - `app.qdrant_store.InMemoryVectorStore`, `set_vector_store`
  - pytest, FastAPI `TestClient`, SQLAlchemy `Session`
- **Wird genutzt von:** Alle Testmodule via pytest-Discovery; explizite Imports:
  - `from app.tests.conftest import create_customer, create_user, login` in `test_admin*.py`, `test_auth.py`, u. a.
- **HTTP / UI / CLI:** `TestClient` simuliert HTTP gegen FastAPI-App; `login()` postet an `POST /login`
- **Daten:** Temporäre SQLite-Datei pro Test (`tmp_path/test.sqlite3`); In-Memory-Qdrant-Ersatz

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `FakeEmbeddings` | Klasse | Test-Double für Embeddings-Backend (konstante 1536-dimensionale Vektoren) |

### Umgebungsvariablen (vor App-Import gesetzt)

| Name | Wert (Default) | Beschreibung |
|---|---|---|
| `OPENAI_API_KEY` | `test-openai-key` | Erfüllt Settings-Validierung ohne echten Key |
| `SESSION_SECRET` | `test-session-secret-for-pytest-only` | Session-Middleware in Tests |

## Funktionen und Klassen

### `FakeEmbeddings`

**Beschreibung:** Liefert deterministische Embedding-Vektoren für Tests ohne OpenAI-Aufruf.

| Methode | Rückgabe | Verhalten |
|---|---|---|
| `embed_documents(texts)` | `list[list[float]]` | Pro Text ein Vektor `[0.01] * 1536` |
| `embed_query(text)` | `list[float]` | Einzelvektor `[0.01] * 1536` |

---

### `fake_embeddings()` (Fixture)

**Beschreibung:** Setzt globalen Embeddings-Backend auf `FakeEmbeddings`, stellt danach wieder her.

**Parameter / Rückgabe:** Yield `FakeEmbeddings`-Instanz.

**Aufrufer / Aufgerufene:** Ruft `set_embeddings_backend`; von `_auto_mock_ai` abhängig.

---

### `fake_vector_store()` (Fixture)

**Beschreibung:** Setzt In-Memory-Vektorstore (`InMemoryVectorStore`, Dim 1536) für Tests.

**Parameter / Rückgabe:** Yield `InMemoryVectorStore`.

**Aufrufer / Aufgerufene:** `set_vector_store`; von `_auto_mock_ai` abhängig.

---

### `_auto_mock_ai(fake_embeddings, fake_vector_store)` (Fixture, autouse)

**Beschreibung:** Aktiviert automatisch KI-Mocks in jedem Test.

**Parameter / Rückgabe:** Keine Rückgabe; yield markiert Fixture-Lebensdauer.

---

### `db_session(tmp_path, monkeypatch) -> Generator[Session]`

**Beschreibung:** Erstellt frische SQLite-DB pro Test, ersetzt Engine/SessionLocal und liefert offene Session.

**Parameter / Rückgabe:**
- `tmp_path` — pytest-Tempverzeichnis
- `monkeypatch` — setzt `DATABASE_URL`
- **Yield:** SQLAlchemy-`Session`

**Ablauf / lokale Variablen:**
- `db_path`, `database_url` — isolierte SQLite-Datei
- `new_engine` — via `db._create_engine`; ersetzt `db.engine` und `db.SessionLocal`
- `config.get_settings.cache_clear()` vor und nach Test

**Aufrufer / Aufgerufene:** Ruft `init_db()`; Basis für `client`-Fixture.

---

### `client(db_session) -> Generator[TestClient]`

**Beschreibung:** FastAPI-TestClient mit überschriebener `get_db`-Dependency.

**Parameter / Rückgabe:** Yield `TestClient(app)`; räumt `dependency_overrides` auf.

**Ablauf / lokale Variablen:** `override_get_db` — yieldet dieselbe `db_session` für alle Requests.

---

### `create_customer(db, customer_id, name) -> Customer`

**Beschreibung:** Legt einen `Customer`-Datensatz an und committed.

**Parameter / Rückgabe:** `db`, Slug `customer_id`, Anzeigename `name` → persistiertes `Customer`.

---

### `create_user(db, email, password="secret123", customer_ids=(), *, is_admin=False) -> User`

**Beschreibung:** Erstellt User mit gehashtem Passwort und optionalen `UserCustomer`-Verknüpfungen.

**Parameter / Rückgabe:**
- `email`, `password`, `customer_ids` — Zuordnungen
- `is_admin` — Admin-Flag
- **Rückgabe:** `User` mit generierter ID `user-{local-part}`

**Ablauf / lokale Variablen:** Validiert jeden Slug via `validate_customer_slug`; wirft `ValueError` bei ungültigem Slug.

---

### `login(client, email, password) -> None`

**Beschreibung:** Führt Form-Login durch und prüft Redirect (302).

**Parameter / Rückgabe:** `TestClient`, Credentials; assertiert Statuscode.

**Aufrufer / Aufgerufene:** POST `/login` mit `follow_redirects=False`.

## Tests

Diese Datei **definiert** Fixtures, enthält aber keine Testfunktionen. Verwendung in Testmodulen:

| Fixture / Hilfe | Typische Nutzer |
|---|---|
| `client`, `db_session` | Fast alle Integrationstests |
| `fake_vector_store` | Explizit z. B. `test_admin_customers.test_rename_tenant_customer_migrates_refs_and_qdrant` |
| `create_customer`, `create_user`, `login` | Admin-, Auth-, Customer-, Chat-Tests |

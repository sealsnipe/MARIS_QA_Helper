# `backend/app/tests/test_auth.py`

**Quellpfad:** `backend/app/tests/test_auth.py`

## Zweck und logischer Aufbau

Tests für **Passwort-Hashing** (`hash_password`, `verify_password`) und **Session-basierte Authentifizierung** über HTTP: geschützte API/HTML ohne Login, Login-Fehler/-Erfolg, Logout.

Die ersten drei Tests sind reine Unit-Tests ohne DB; die restlichen nutzen `client` und teils `db_session` mit Conftest-Helfern.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.auth.hash_password`, `verify_password`
  - `app.tests.conftest.create_user` (in `test_login_failure_shows_generic_error`)
  - Später in Session-Tests: `create_customer`, `create_user`, `login` aus Conftest
- **Wird genutzt von:** pytest
- **HTTP / UI:** `GET /api/me`, `GET /chat`, `POST /login`, `POST /logout`, `GET /login?error=1`
- **Daten:** SQLite für User/Mandant in Session-Tests
- **Abgedecktes Modul:** `backend/app/auth.py`, `backend/app/routes.py` (Login/Logout/Me)

## Konstanten, Typen und Modulebene

Keine Modulebenen-Symbole außer Testfunktionen.

## Funktionen und Klassen

### `test_hash_verify_roundtrip()`

**Beschreibung:** Gehashtes Passwort verifiziert korrekt; Hash unterscheidet sich vom Klartext.

**Parameter / Rückgabe:** Keine Parameter.

**Ablauf / lokale Variablen:** `password`, `password_hash` — Roundtrip mit `verify_password`.

**Aufrufer / Aufgerufene:** `hash_password`, `verify_password` in `auth.py`.

---

### `test_verify_rejects_wrong_password()`

**Beschreibung:** Falsches Passwort schlägt bei `verify_password` fehl.

**Ablauf / lokale Variablen:** Hash von `"correct"`, Prüfung mit `"wrong"`.

---

### `test_two_hashes_differ()`

**Beschreibung:** Zwei Hashes desselben Passworts sind unterschiedlich (Salt).

**Ablauf / lokale Variablen:** `first`, `second` — beide `hash_password("same-password")`.

---

### `test_get_current_user_without_session_returns_401(client)`

**Beschreibung:** Ohne Session liefert `GET /api/me` 401 und `{"error": "not_authenticated"}`.

**Parameter / Rückgabe:** `client` — TestClient.

---

### `test_protected_html_redirects_to_login(client)`

**Beschreibung:** Ungeschützter Zugriff auf `/chat` → 302 `/login`.

---

### `test_login_failure_shows_generic_error(client, db_session)`

**Beschreibung:** Falsches Passwort → Redirect `/login?error=1` und Fehlermeldung auf Login-Seite.

**Ablauf / lokale Variablen:** User `user@example.com`; `page` — HTML mit Text „E-Mail oder Passwort falsch“.

---

### `test_login_success_sets_session(client, db_session)`

**Beschreibung:** Erfolgreicher Login: `GET /api/me` liefert E-Mail und `active_customer` für Ein-Mandanten-User.

**Ablauf / lokale Variablen:** Mandant `kkrr`, User `single@example.com`; `body` aus `/api/me`.

---

### `test_logout_clears_session(client, db_session)`

**Beschreibung:** `POST /logout` → Redirect; danach `/api/me` → 401.

## (Optional) Tests

- **Fixtures:** `client` (alle HTTP-Tests), `db_session` (Session-Tests); autouse KI-Mocks irrelevant für Auth. Helfer: `create_user`, `create_customer`, `login`.
- **Abgedecktes Modul:** `backend/app/auth.py`, `backend/app/routes.py`.

| Test | Intent |
|---|---|
| `test_hash_verify_roundtrip` | Hash/Verify konsistent |
| `test_verify_rejects_wrong_password` | Falsches PW abgelehnt |
| `test_two_hashes_differ` | Salzung wirksam |
| `test_get_current_user_without_session_returns_401` | API ohne Session |
| `test_protected_html_redirects_to_login` | HTML-Schutz |
| `test_login_failure_shows_generic_error` | Generische Login-Fehlermeldung |
| `test_login_success_sets_session` | Session + `/api/me` |
| `test_logout_clears_session` | Session nach Logout weg |
| `test_login_rate_limit_after_many_fails` | 10 fails normal error=1; 11th rate_limited; success nach Rate resettet Zähler (F5) |

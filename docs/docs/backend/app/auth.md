# `backend/app/auth.py`

**Quellpfad:** `backend/app/auth.py`

## Zweck und logischer Aufbau

Authentifizierungs- und Autorisierungshilfen für FastAPI: Passwort-Hashing (Argon2), Session-basierte Benutzerauflösung und Admin-Guard. Die Session speichert `user_id` (gesetzt in `routes.py` beim Login); `get_current_user` liest diese ID und lädt den aktiven `User` aus SQLite.

Lesereihenfolge: Modul-Passwort-Hasher → Exception-Klassen → `hash_password` / `verify_password` → DB-Lookup `get_user_by_email` → FastAPI-Dependencies `get_current_user`, `get_admin_user`.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `argon2.PasswordHasher`, `VerifyMismatchError`
  - `fastapi.Depends`, `Request`
  - `app.db.get_db`
  - `app.models.User`
- **Wird genutzt von:**
  - `backend/app/routes.py` — Login, Session, alle geschützten Endpoints
  - `backend/app/tenant.py` — `get_current_user`, `NotAuthenticatedError`
  - `backend/app/users_admin.py` — `hash_password`
  - `scripts/seed_users.py` — `hash_password`
  - `backend/app/tests/conftest.py`, `test_auth.py`
- **HTTP / UI:** Session-Cookie `session` (Middleware in `main.py`); Redirect `/login` bei 401 für HTML
- **Daten:** SQLite-Tabelle `users` (`User`-ORM)

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `_password_hasher` | `PasswordHasher` (Modul-Privat) | Singleton Argon2-Hasher |
| `NotAuthenticatedError` | Exception | Keine oder ungültige Session |
| `ForbiddenError` | Exception | Nutzer ohne Admin-Rechte |

## Funktionen und Klassen

### `hash_password(plaintext: str) -> str`

**Beschreibung:** Erzeugt einen Argon2-Hash für ein Klartext-Passwort.

**Parameter / Rückgabe:** `plaintext` → Hash-String.

**Aufrufer / Aufgerufene:** `_password_hasher.hash`; Aufrufer: `users_admin.py`, Seed-Skripte, Tests.

---

### `verify_password(password_hash: str, plaintext: str) -> bool`

**Beschreibung:** Prüft Passwort gegen gespeicherten Hash; bei Mismatch `False` (kein Exception-Leak).

**Parameter / Rückgabe:** Hash und Klartext → `bool`.

**Aufrufer / Aufgerufene:** `_password_hasher.verify`; Aufrufer: `routes.py` (Login), Tests.

---

### `get_user_by_email(db: Session, email: str) -> User | None`

**Beschreibung:** Sucht Benutzer per normalisierter E-Mail (trim, lower).

**Parameter / Rückgabe:** DB-Session und E-Mail → `User` oder `None`.

**Ablauf / lokale Variablen:** `normalized` — bereinigte E-Mail für SQL-Query.

**Aufrufer / Aufgerufene:** SQLAlchemy `select(User)`; Aufrufer: `routes.py` (Login).

---

### `get_current_user(request: Request, db: Session = Depends(get_db)) -> User`

**Beschreibung:** FastAPI-Dependency: löst eingeloggten Benutzer aus Session-Cookie auf.

**Parameter / Rückgabe:** Request mit Session → aktiver `User`.

**Ablauf / lokale Variablen:**
- `user_id` aus `request.session`
- Bei fehlendem/inaktivem User: Session leeren, `NotAuthenticatedError`

**Aufrufer / Aufgerufene:** `db.get(User, user_id)`; Aufrufer: fast alle `routes.py`-Handler, `tenant.py`.

---

### `get_admin_user(user: User = Depends(get_current_user)) -> User`

**Beschreibung:** Erfordert Admin-Flag auf dem authentifizierten User.

**Parameter / Rückgabe:** `User` → gleicher User oder `ForbiddenError`.

**Aufrufer / Aufgerufene:** Hängt von `get_current_user` ab; Aufrufer: Admin-Routen in `routes.py`.

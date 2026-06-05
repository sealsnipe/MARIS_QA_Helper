# `backend/app/integration_auth.py`

**Quellpfad:** `backend/app/integration_auth.py`

## Zweck und logischer Aufbau

Auth für die Maschinen-API (`/api/v1/*`): Bearer-Token-Validierung gegen `INTEGRATION_API_TOKEN` (aus Settings), Mapping auf dedizierten `integration@internal` User. Getrennt von Session-Auth.

Einstieg für Integration-Router: `get_integration_user` (Header-Dep).

Fehler: `IntegrationDisabledError` (kein/leerer Token in Env), `InvalidIntegrationTokenError`, `IntegrationUserNotFoundError`.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.auth.get_user_by_email`
  - `app.config.get_settings`
  - `app.db.get_db`
  - `app.models.User`
  - `fastapi.Header`, `secrets.compare_digest`
- **Wird genutzt von:** `app.integration_routes` (Depends), `main.py` (Exception-Handler für die Errors)
- **HTTP / UI:** `Authorization: Bearer <token>` auf `/api/v1/ask` und `/api/v1/knowledge-content`
- **Daten:** Users (per Email), Settings (INTEGRATION_*)

## Konstanten, Typen und Modulebene

Keine.

## Funktionen und Klassen

### `IntegrationDisabledError`, `InvalidIntegrationTokenError`, `IntegrationUserNotFoundError`

Spezifische Exceptions (werden in main zu 401/503 JSON).

### `_extract_bearer_token(authorization: str | None) -> str | None`

Parst "Bearer xxx"; robust gegen Whitespace/Fehlform.

### `get_integration_user(authorization=Header..., db=Depends(get_db)) -> User`

- Prüft `settings.integration_enabled` (bool(token.strip())) → DisabledError.
- Extrahiert + `compare_digest` gegen `INTEGRATION_API_TOKEN`.
- Lädt User per `INTEGRATION_USER_EMAIL`; active-Check.
- Wird als Depends in v1-Routen verwendet (erzeugt "integration user" Kontext).

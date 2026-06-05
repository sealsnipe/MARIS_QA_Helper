# `backend/app/oauth_device_flow.py`

**Quellpfad:** `backend/app/oauth_device_flow.py`

## Zweck und logischer Aufbau

Device-Flow + Token-Refresh für ChatGPT/Codex OAuth (LLM_AUTH_MODE). Ermöglicht Admin-Keys-UI, Tokens ohne festen API-Key zu setzen (device code in Browser, Polling).

Wird von `secrets_admin.py` / Admin-Keys-Routes genutzt. Keine Session- oder Tenant-Abhängigkeit.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `app.config.get_settings`, `httpx`, json, pathlib, time, stat
- **Wird genutzt von:** `app.secrets_admin` (start/poll/refresh), Admin-Keys UI + API (`/api/admin/keys/*`)
- **HTTP / UI:** Admin /admin/keys (OAuth Device Flow Buttons)
- **Daten:** FS `~/.codex/auth.json` oder `~/.oauth_codex/auth.json` (je nach Mode); kein DB.

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `CLIENT_ID` | str | "app_EMoamEEZ73f0CkXaXp7hrann" (OpenAI Device) |
| `AUTH_ORIGIN` | str | "https://auth.openai.com" |
| `DEVICE_*_URL` | str | Usercode / Token / Verify / Redirect URIs |
| `OAUTH_TOKEN_URL` | str | Für Refresh |
| `POLL_TIMEOUT_SECONDS` | int | 15*60 |

## Funktionen und Klassen

### `_jwt_account_id(access_token) -> str | None`

Decoded JWT-Payload (base64), extrahiert chatgpt_account_id oder account_id.

### `_save_tokens(target: Path, token_payload)`

Schreibt standardisiertes Token-JSON (access/refresh/id, account_id, last_refresh); chmod 600.

### `start_device_flow() -> dict`

POST usercode → gibt device_code, user_code, verification_uri etc. zurück (für UI-Poll).

### `poll_device_token(device_code) -> dict`

Polling-Loop (bis Timeout oder success); POST token mit grant device; bei authorization_pending → sleep/retry; speichert via _save_tokens in codex_oauth_auth_path.

### `refresh_access_token(refresh_token) -> dict | None`

POST oauth/token (refresh grant) → neues access; speichert; None bei Fehler.

### `load_stored_tokens() -> dict | None`

Liest aus codex_oauth oder fallback codex path; None bei Fehlen/Fehler.

### `get_effective_access_token(db=None) -> str | None`

Gibt stored access oder None (für LLM-Client in oauth mode).

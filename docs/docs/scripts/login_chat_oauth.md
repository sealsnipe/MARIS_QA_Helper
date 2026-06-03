# `scripts/login_chat_oauth.py`

**Quellpfad:** `scripts/login_chat_oauth.py`

## Zweck und logischer Aufbau

Führt **ChatGPT OAuth Device-Code-Flow** auf Ubuntu/WSL durch (ohne Windows-Codex): Nutzer öffnet URL, gibt Einmalcode ein; Tokens landen nur im Linux-Dateisystem unter `~/.oauth_codex/auth.json`.

Reihenfolge: Modul-Konstanten (URLs, `CLIENT_ID`) → JWT-Helfer → HTTP-Schritte (`_create_device_session`, `_poll_device_token`, `_exchange_code`) → `login_device_code` → CLI.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `httpx` (HTTP-Client)
- **Wird genutzt von:** `scripts/setup.py` (`login_device_code`); manuell; Hinweis in `smoke_chat_oauth.py`
- **HTTP:** `auth.openai.com` Device- und Token-Endpoints, `OAUTH_TOKEN_URL`
- **Dateisystem:** `DEFAULT_TARGET` = `~/.oauth_codex/auth.json`

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `CLIENT_ID` | `str` | OpenAI App-ID für Device Auth |
| `AUTH_ORIGIN` | `str` | `https://auth.openai.com` |
| `DEVICE_USERCODE_URL` | `str` | POST Usercode |
| `DEVICE_TOKEN_URL` | `str` | Poll Token |
| `DEVICE_VERIFY_URL` | `str` | Browser-URL für Nutzer |
| `DEVICE_REDIRECT_URI` | `str` | OAuth redirect |
| `OAUTH_TOKEN_URL` | `str` | Code → Access Token |
| `DEFAULT_TARGET` | `Path` | Ziel-`auth.json` |
| `POLL_TIMEOUT_SECONDS` | `int` | `15 * 60` |

## Funktionen und Klassen

### `_jwt_account_id(access_token: str) -> str | None`

**Beschreibung:** Liest `chatgpt_account_id` aus JWT-Claim `https://api.openai.com/auth` oder `account_id`.

---

### `_jwt_expires_at(access_token: str) -> float | None`

**Beschreibung:** JWT `exp` als float.

---

### `_save_tokens(target: Path, token_payload: dict) -> None`

**Beschreibung:** Schreibt normalisiertes Dict (`access_token`, `refresh_token`, `account_id`, `expires_at`, `last_refresh=time.time()`) mit Modus `0600`.

---

### `_create_device_session(client: httpx.Client) -> dict`

**Beschreibung:** POST `DEVICE_USERCODE_URL` mit `client_id`; erwartet `device_auth_id`, `user_code`.

---

### `_poll_device_token(client, device_auth_id, user_code, interval) -> dict`

**Beschreibung:** Pollt bis `authorization_code` und `code_verifier` da sind oder Timeout.

**Ablauf:** Bei 403/404 weiter warten; `deadline` aus `POLL_TIMEOUT_SECONDS`.

---

### `_exchange_code(client, authorization_code, code_verifier) -> dict`

**Beschreibung:** Authorization-Code-Grant gegen `OAUTH_TOKEN_URL`.

---

### `login_device_code(target: Path) -> None`

**Beschreibung:** Kompletter interaktiver Flow mit Konsolen-Anweisungen; ruft `_save_tokens` am Ende.

---

### `parse_args() / main()`

**Beschreibung:** `--target`; fängt `KeyboardInterrupt` und andere Exceptions mit `SystemExit`.

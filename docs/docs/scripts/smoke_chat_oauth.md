# `scripts/smoke_chat_oauth.py`

**Quellpfad:** `scripts/smoke_chat_oauth.py`

## Zweck und logischer Aufbau

Manueller **Smoke-Test** für den Chat-Backend-Pfad über **ChatGPT OAuth** (Codex `/responses` SSE). Embeddings bleiben separat über `OPENAI_API_KEY`. Probiert bevorzugtes Modell aus `.env`, dann Fallback-Liste `CODEX_MODELS`.

Ablauf: OAuth-Datei prüfen → `oauth_codex.Client` authentifizieren → Streaming-POST → Delta-Events sammeln → Antwort muss nicht leer sein.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `httpx`; `app.config.get_settings`; Paket `oauth_codex` (`Client`, `FileTokenStore`)
- **Wird genutzt von:** manuell nach `login_chat_oauth.py` oder `import_codex_auth.py`
- **HTTP:** `{CODEX_BASE_URL}/responses` (SSE)
- **Env:** `LLM_AUTH_MODE`, `CHAT_MODEL`, `CODEX_BASE_URL`, `OPENAI_BASE_URL`

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `ROOT` | `Path` | Repo-Root |
| `DEFAULT_OAUTH_AUTH` | `Path` | `~/.oauth_codex/auth.json` |
| `CODEX_MODELS` | `tuple` | `gpt-5.4-mini`, `gpt-5.3-codex-spark`, … |
| `DEFAULT_INSTRUCTIONS` | `str` | System-Prompt für Mini-Antwort „OK“ |

## Funktionen und Klassen

### `_ensure_oauth_auth(path: Path) -> None`

**Beschreibung:** `SystemExit` mit Hinweis auf `login_chat_oauth.py`, wenn Datei fehlt.

---

### `_auth_headers(auth_path: Path) -> dict[str, str]`

**Beschreibung:** Baut authentifizierte Headers inkl. `Accept: text/event-stream`.

**Aufrufer / Aufgerufene:** `get_settings`, `Client.authenticate()`, `client.auth.get_headers()`.

---

### `_run_chat(model: str, auth_path: Path) -> tuple[str, str]`

**Beschreibung:** POST mit `stream=True`, parst SSE-Zeilen `data: …`, sammelt `response.output_text.delta`.

**Ablauf / lokale Variablen:** `parts` — Liste der Delta-Strings; `answer` — zusammengefügt und gestrippt.

---

### `parse_args() / main()`

**Beschreibung:** Optional `--model`; Schleife über Modellliste; bei expired/401 Hinweis Re-Login; sonst `SystemExit` wenn alle Versuche scheitern.

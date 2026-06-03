# `backend/app/config.py`

**Quellpfad:** `backend/app/config.py`

## Zweck und logischer Aufbau

Zentrale Anwendungskonfiguration via Pydantic Settings: Umgebungsvariablen und `.env` werden in ein typisiertes `Settings`-Objekt geladen. Pflichtfelder (`SESSION_SECRET`, `OPENAI_API_KEY`) werden validiert; abgeleitete Properties liefern Upload-Limits, Extension-Sets und OAuth-Pfade.

Lesereihenfolge: Typalias `LLMAuthMode` → Klasse `Settings` (Felder, Validator, Properties) → gecachtes `get_settings()`. Fast jedes Backend-Modul ruft `get_settings()` beim Import oder zur Laufzeit auf.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `functools.lru_cache`
  - `pydantic.field_validator`
  - `pydantic_settings.BaseSettings`, `SettingsConfigDict`
- **Wird genutzt von:**
  - `backend/app/main.py`, `db.py`, `agent.py`, `llm.py`, `embeddings.py`, `retrieval.py`, `upload.py`, `qdrant_store.py`
  - `scripts/smoke_openai.py`, `scripts/smoke_chat_oauth.py`
  - `backend/app/tests/conftest.py` — `cache_clear()` zwischen Tests
- **HTTP / UI:** indirekt — Session-Middleware, Upload-Limits, Retrieval-Defaults
- **Daten:** liest `.env` / Prozess-Env; keine DB

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `LLMAuthMode` | `Literal["api_key", "chatgpt_oauth"]` | Erlaubte Werte für `LLM_AUTH_MODE` |
| `Settings` | Pydantic-Model | Alle Konfigurationsfelder mit Defaults und Validierung |
| `get_settings` | Funktion (`@lru_cache`) | Singleton-Zugriff auf `Settings()` |

### `Settings` — Felder

| Feld | Default | Beschreibung |
|---|---|---|
| `APP_HOST` | `0.0.0.0` | Server-Bind |
| `APP_PORT` | `8088` | HTTP-Port |
| `SESSION_SECRET` | *(Pflicht)* | Session-Signatur |
| `DATABASE_URL` | `sqlite:///./data/support_kb.sqlite3` | SQLAlchemy-URL |
| `QDRANT_URL` | `http://qdrant:6333` | Qdrant-REST |
| `COLLECTION_PREFIX` | `kb_` | Collection-Präfix |
| `OPENAI_API_KEY` | *(Pflicht)* | API-Key |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI-kompatible Basis |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding-Modell |
| `EMBEDDING_DIM` | `1536` | Vektordimension |
| `LLM_AUTH_MODE` | `chatgpt_oauth` | Chat-Auth-Modus |
| `CHAT_MODEL` | `gpt-4.1-mini` | Chat-Modell (Code-Default; `.env` kann überschreiben) |
| `CODEX_AUTH_PATH` | `~/.codex/auth.json` | Codex-Auth-Pfad |
| `CODEX_OAUTH_AUTH_PATH` | `~/.oauth_codex/auth.json` | OAuth-Auth-Pfad |
| `CODEX_BASE_URL` | ChatGPT Codex-URL | Codex-Backend |
| `SESSION_COOKIE_SECURE` | `False` | HTTPS-only Cookies |
| `TOP_K_DEFAULT` | `4` | Retrieval Top-K |
| `MIN_SCORE_DEFAULT` | `0.25` | Mindest-Score |
| `MAX_TOOL_ROUNDS` | `4` | Agent-Tool-Runden |
| `MAX_UPLOAD_MB` | `30` | Upload-Limit MB |
| `ALLOWED_EXTENSIONS` | `.txt,.md,.pdf,.docx` | Komma-separierte Endungen |

`model_config`: liest `.env`, `extra="ignore"`.

## Funktionen und Klassen

### `Settings.must_not_be_empty` (Validator)

**Beschreibung:** `@field_validator` für `SESSION_SECRET` und `OPENAI_API_KEY` — leer/Whitespace → `ValueError`.

**Aufrufer / Aufgerufene:** Pydantic beim Instanziieren.

---

### `Settings.allowed_extensions` (`@property`)

**Beschreibung:** Parst `ALLOWED_EXTENSIONS` in lowercase-`set[str]`.

**Aufrufer / Aufgerufene:** Aufrufer: `upload.py`.

---

### `Settings.max_upload_bytes` (`@property`)

**Beschreibung:** `MAX_UPLOAD_MB * 1024 * 1024`.

**Aufrufer / Aufgerufene:** Aufrufer: `upload.py`.

---

### `Settings.codex_oauth_auth_path` (`@property`)

**Beschreibung:** Expandiert `~` in `CODEX_OAUTH_AUTH_PATH` via `Path.expanduser()`.

**Aufrufer / Aufgerufene:** Aufrufer: `llm.py`.

---

### `Settings.uses_chatgpt_oauth` (`@property`)

**Beschreibung:** `True`, wenn `LLM_AUTH_MODE == "chatgpt_oauth"`.

**Aufrufer / Aufgerufene:** Aufrufer: `llm.py`.

---

### `get_settings() -> Settings`

**Beschreibung:** Liefert gecachte `Settings`-Instanz (einmal pro Prozess, bis `cache_clear()`).

**Aufrufer / Aufgerufene:** Breit im Backend und in Smoke-Skripten; Tests leeren Cache in `conftest.py`.

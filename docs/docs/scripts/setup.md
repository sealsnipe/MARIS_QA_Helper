# `scripts/setup.py`

**Quellpfad:** `scripts/setup.py`

## Zweck und logischer Aufbau

**Interaktives Erst-Setup** der MARIS Q/A Helper-Instanz: `.env` aus Example, OpenAI-Key für Embeddings, Chat-Auth (`api_key` vs. `chatgpt_oauth`), Deploy-Profil (`dev`/`prod`), Runtime (`docker`/`local`), Docker-Preflight, optional Compose-Start und Seed (Kunden + Admin). Non-interactive Modus für CI/Install-Skripte.

Lesereihenfolge: Pfad-/Compose-Konstanten → Env-Helfer (`_read_lines`, `_upsert`, …) → Prompts/Validierung → Profil/Runtime/LLM-Auflösung → Chat/OAuth/Deploy-Konfiguration → Compose-Befehle → Seed/Next-Steps → `parse_args` → `main`.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `docker_preflight` (`ensure_docker`, `assert_docker_ready`, `run_with_docker_session`); `login_chat_oauth.login_device_code`; `seed_setup.run_seed`; Compose-Dateien `docker-compose.yml`, `.prod.yml`, `.oauth.yml`
- **Wird genutzt von:** `install.sh`, manuell `python3 scripts/setup.py`
- **CLI:** viele Flags (`--non-interactive`, `--openai-key`, `--profile`, `--start`, …)
- **Daten:** schreibt `ROOT/.env`; Seed in SQLite via `seed_setup` oder `docker compose exec api`

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `ROOT` | `Path` | Repo-Root |
| `ENV_PATH` / `EXAMPLE_PATH` | `Path` | `.env` / `.env.example` |
| `COMPOSE_BASE` / `COMPOSE_PROD` / `COMPOSE_OAUTH` | `Path` | Compose-Stacks |
| `DEFAULT_OAUTH_PATH` | `Path` | `~/.oauth_codex/auth.json` |
| `DEFAULT_ADMIN_EMAIL` | `str` | `matthias.schindler@maris-healthcare.de` |
| `PLACEHOLDER_KEY` | `str` | Platzhalter in Example |
| `KEY_PATTERN` | `re.Pattern` | OpenAI-Key-Format |
| `CHAT_MODEL_API` / `CHAT_MODEL_OAUTH` | `str` | `gpt-4.1-mini` / `gpt-5.4-mini` |
| `DeployProfile` | `Literal` | `dev` \| `prod` |
| `Runtime` | `Literal` | `docker` \| `local` |
| `LlmAuthMode` | `Literal` | `api_key` \| `chatgpt_oauth` |

## Funktionen und Klassen

### `_read_lines(path) -> list[str]`

**Beschreibung:** Liest Env-Datei zeilenweise.

---

### `_write_env(lines) -> None`

**Beschreibung:** Schreibt `ENV_PATH`.

---

### `_upsert(lines, key, value) -> list[str]`

**Beschreibung:** Ersetzt oder appendet `KEY=value`.

---

### `_get_value(lines, key, default="") -> str`

**Beschreibung:** Liest einen Key aus Zeilenliste.

---

### `_validate_openai_key(value) -> str`

**Beschreibung:** Lehnt Platzhalter ab; Regex-Check.

---

### `_prompt_yes_no(question, default=False) -> bool`

**Beschreibung:** Interaktive Ja/Nein-Schleife.

---

### `_prompt_choice(question, options) -> str`

**Beschreibung:** Nummerierte oder Key-Auswahl aus `list[tuple[key, label]]`.

---

### `_check_prerequisites(*, skip_docker, runtime, interactive, auto_install_docker)`

**Beschreibung:** Python-Version; bei `runtime=docker` → `ensure_docker`, sonst optional übersprungen.

**Rückgabe:** `DockerStatus` oder `None`.

---

### `_require_docker_ready(status) -> None`

**Beschreibung:** `assert_docker_ready` vor Compose.

---

### `_ensure_env_file() -> list[str]`

**Beschreibung:** Bestehende `.env` oder Kopie von `.env.example`.

---

### `_resolve_deploy_profile(args) -> DeployProfile`

**Beschreibung:** Flag `--profile`, oder `--production` → `prod`, oder Prompt.

---

### `_resolve_runtime(args, profile) -> Runtime`

**Beschreibung:** `docker` vs. `local` (non-interactive default `docker`).

---

### `_resolve_llm_mode(args, profile) -> LlmAuthMode`

**Beschreibung:** API-Key vs. OAuth; in Prod Warnung bei OAuth.

---

### `_mask_key_preview(key) -> str`

**Beschreibung:** Anzeige-Maske für Keys.

---

### `_prompt_openai_key_interactive() -> str`

**Beschreibung:** Sichtbare Eingabe mit Validierung.

---

### `_prompt_embedding_key(lines, *, openai_key, interactive) -> tuple[list[str], str]`

**Beschreibung:** Erklärt Embedding-Pflicht; übernimmt CLI-Key, vorhandenen Key oder Prompt.

---

### `_configure_chat_api_key(lines) -> list[str]`

**Beschreibung:** Setzt `LLM_AUTH_MODE=api_key`, `CHAT_MODEL=CHAT_MODEL_API`.

---

### `_configure_chat_oauth(lines, *, oauth_path, skip_login) -> list[str]`

**Beschreibung:** OAuth-Env; optional `login_device_code` (braucht `httpx` auf Host).

---

### `_configure_runtime(lines, *, runtime) -> list[str]`

**Beschreibung:** `QDRANT_URL` → `http://qdrant:6333` (docker) oder `http://127.0.0.1:6333` (local).

---

### `_configure_deploy(lines, *, profile) -> list[str]`

**Beschreibung:** `SESSION_COOKIE_SECURE`, `DEPLOY_PROFILE`.

---

### `_ensure_session_secret(lines) -> list[str]`

**Beschreibung:** Generiert `secrets.token_urlsafe(48)` wenn schwach/fehlend.

---

### `_compose_file_args(profile, llm_mode) -> list[str]`

**Beschreibung:** `-f` Basis; prod → `.prod.yml`; dev+oauth → `.oauth.yml`.

---

### `_prompt_admin_credentials(*, interactive, admin_email, admin_password) -> tuple[str, str]`

**Beschreibung:** E-Mail + Passwort für Seed; non-interactive braucht `--admin-password` oder `SEED_ADMIN_PASSWORD`.

---

### `_compose_command(profile, llm_mode, oauth_path) -> list[str]`

**Beschreibung:** `docker compose … up --build -d`.

---

### `_compose_env(profile, llm_mode, oauth_path) -> dict[str, str]`

**Beschreibung:** Kopiert `os.environ`; bei dev+oauth setzt `OAUTH_AUTH_HOST_PATH` wenn Datei existiert.

---

### `_format_compose_hint(cmd, env) -> str`

**Beschreibung:** Shell-quotierte Kommandozeile inkl. OAuth-Prefix.

---

### `_maybe_start_compose(*, start, runtime, profile, llm_mode, oauth_path, docker_status) -> bool`

**Beschreibung:** Überspringt bei `local` oder `--no-start`; sonst `run_with_docker_session` mit `_compose_command`.

**Rückgabe:** `True` wenn Stack gestartet.

---

### `_maybe_run_seed(*, runtime, profile, llm_mode, oauth_path, admin_email, admin_password, compose_started, skip_seed) -> bool`

**Beschreibung:** Docker: `compose exec api python scripts/seed_setup.py` mit Env-Vars; local: `run_seed` direkt.

---

### `_compose_start_hint(profile, llm_mode, oauth_path) -> str`

**Beschreibung:** String für manuellen Start in Next-Steps.

---

### `_print_next_steps(*, profile, runtime, llm_mode, oauth_path, admin_email, seeded) -> None`

**Beschreibung:** Abschluss-Checkliste (URLs, Logs, Seed, `update.sh`, Smoke-Skripte, pytest).

---

### `parse_args() -> argparse.Namespace`

**Beschreibung:** Alle CLI-Flags (`--openai-key`, `--llm-auth-mode`, `--profile`, `--runtime`, `--oauth-path`, `--skip-oauth-login`, `--skip-docker-check`, `--skip-seed`, Admin-Creds, `--install-docker`, `--no-start`, `--start`, `--non-interactive`, …).

---

### `main() -> None`

**Beschreibung:** Orchestriert gesamten Wizard: Profil/Runtime/Preflight → Env-Zeilen → Embedding → Chat-Modus → Runtime/Deploy/Secret → schreiben → Admin-Creds → Compose → Seed → Next steps.

**Ablauf / lokale Variablen:** `compose_started`, `seeded` — steuern Hinweise in `_print_next_steps`.

**Aufrufer / Aufgerufene:** siehe Traces oben; `KeyboardInterrupt` → `SystemExit` im `__main__`-Guard.

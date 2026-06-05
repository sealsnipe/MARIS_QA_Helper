# `backend/app/secrets_admin.py`

**Quellpfad:** `backend/app/secrets_admin.py`

## Zweck und logischer Aufbau

Administrierbare Secrets (Chat/Embed/Similarity/Integration Keys + Auth-Modes) — Persistenz in `app_secrets` (DB), Masking, effective-Lookup (DB override > .env Fallback).

Unterstützt OAuth-Device-Flow für chatgpt_oauth Mode.

Genutzt von /admin/keys UI + LLM/Embed-Clients.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.config.get_settings`
  - `app.db.SessionLocal`
  - `app.models.AppSecret`
  - `app.oauth_device_flow` (start/poll/refresh/load/get_effective)
  - pathlib, json
- **Wird genutzt von:** `app.routes` (Admin-Keys Endpoints), `app.llm`, `app.embeddings`, `app.retrieval` (ähnlich), Integration-Config
- **HTTP / UI:** /admin/keys (GET list masked + effective, PATCH set, DELETE clear, OAuth-Device Start/Poll)
- **Daten:** app_secrets (name PK, value, updated_*)

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `KNOWN_SECRETS` | set | chat_api_key, chat_auth_mode, embedding_api_key, similarity_mode, similarity_api_key, similarity_auth_mode, integration_api_token |

`SecretsAdminError(...)`

## Funktionen und Klassen

### Mask / DB
- `_is_valid_secret_name`, `_mask_value`
- `_get_db_secret(db, name)`
- `get_effective_secret(db, name)` (DB oder Settings-Fallback; für integration auch empty erlaubt)

### Keys / Modes
- `list_admin_keys(db)` → dict mit masked + effective + modes + oauth_status
- `set_admin_key(db, name, value)` (valid + store or delete if empty for some)
- `clear_admin_key(db, name)`
- `get_chat_auth_mode(db)`, `get_similarity_mode(db)` etc.

### OAuth Device (delegiert)
- `start_oauth_device_flow()`
- `poll_oauth_device_token(device_code)`
- `refresh_oauth_token()`
- `get_oauth_status()`

Wird vor LLM-Calls in oauth-Mode genutzt, um effective Token zu laden.

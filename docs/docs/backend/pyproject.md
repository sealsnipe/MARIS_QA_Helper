# `backend/pyproject.toml`

**Quellpfad:** `backend/pyproject.toml`

## Zweck

Python-Projektmetadaten und Abhängigkeitsliste für das Backend-Paket `app`. Wird vom `backend/Dockerfile` beim Image-Build per `pip install` ausgewertet und definiert pytest-Pfade für Tests unter `app/tests`.

## Ablauf (kurz)

1. `[project]`: Name `sup-qa-helper`, Version `0.1.0`, Python `>=3.12`, Runtime-Dependencies.
2. `[build-system]`: Hatchling als Build-Backend.
3. `[tool.hatch.build.targets.wheel]`: Wheel-Paket `app`.
4. `[tool.pytest.ini_options]`: Tests in `app/tests`, `pythonpath` = `.` (relativ zu `backend/` beim pytest-Aufruf).

## Konfiguration / Parameter

| Abschnitt | Schlüssel | Wert / Inhalt |
|---|---|---|
| `[project]` | `name` | `sup-qa-helper` |
| `[project]` | `version` | `0.1.0` |
| `[project]` | `requires-python` | `>=3.12` |
| `[build-system]` | `requires` | `hatchling` |
| `[build-system]` | `build-backend` | `hatchling.build` |
| `[tool.hatch.build.targets.wheel]` | `packages` | `["app"]` |
| `[tool.pytest.ini_options]` | `testpaths` | `["app/tests"]` |
| `[tool.pytest.ini_options]` | `pythonpath` | `["."]` |

**Runtime-Dependencies (`dependencies`):**

| Paket | Mindestversion (Auszug) |
|---|---|
| `fastapi` | `>=0.115` |
| `uvicorn[standard]` | `>=0.32` |
| `jinja2` | `>=3.1` |
| `python-multipart` | `>=0.0.9` |
| `sqlalchemy` | `>=2.0` |
| `qdrant-client` | `>=1.12` |
| `openai` | `>=1.55` |
| `argon2-cffi` | `>=23.1` |
| `pypdf` | `>=5.0` |
| `python-docx` | `>=1.1` |
| `pytest` | `>=8.0` |
| `httpx` | `>=0.27` |
| `pydantic-settings` | `>=2.0` |
| `itsdangerous` | `>=2.2` |
| `oauth-codex` | `>=0.1` |

## Siehe auch

- [`docs/docs/backend/Dockerfile.md`](./Dockerfile.md) — installiert Abhängigkeiten aus dieser Datei
- [`docs/docs/backend/app/main.md`](./app/main.md) — FastAPI-Einstieg
- [`docs/docs/backend/app/config.md`](./app/config.md) — Laufzeit-Settings (`.env`, nicht pyproject)

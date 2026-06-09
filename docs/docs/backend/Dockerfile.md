# `backend/Dockerfile`

**Quellpfad:** `backend/Dockerfile`

## Zweck

Multi-Stage-freies Container-Image für die FastAPI-Anwendung. Baut ein schlankes Python-3.12-Image, installiert Backend-Abhängigkeiten und startet Uvicorn mit `app.main:app` auf Port 8088. Wird von `docker-compose.yml` und `docker-compose.prod.yml` referenziert.

## Ablauf (kurz)

1. Basis: `python:3.12-slim`, Arbeitsverzeichnis `/app`.
2. `apt-get` install poppler-utils (für pdfimages / originale Embed-Qualität im Vision-OCR-Pfad; Fallback pypdf immer verfügbar).
3. `backend/pyproject.toml` kopieren; Python-Pakete per `pip install` (FastAPI, SQLAlchemy, Qdrant, OpenAI, Argon2, PDF/DOCX, pytest, …).
4. Anwendungscode: `backend/app` → `/app/app`, `scripts/` → `/app/scripts`.
5. `PYTHONPATH=/app`, Port 8088 exponiert.
6. Start: `uvicorn app.main:app --host 0.0.0.0 --port 8088 --workers 1`.

## Konfiguration / Parameter

| Aspekt | Wert | Beschreibung |
|---|---|---|
| Basis-Image | `python:3.12-slim` | Laufzeit |
| `WORKDIR` | `/app` | Container-Arbeitsverzeichnis |
| `ENV PYTHONPATH` | `/app` | Import-Pfad für `app.*` |
| `EXPOSE` | `8088` | HTTP-Port |
| `CMD` | Uvicorn 1 Worker | Einstieg `app.main:app` |
| poppler-utils (apt) | installiert | pdfimages für bessere Embed-Extraktion (optional, pypdf-Fallback) |
| Umgebung | `.env` via Compose | Nicht im Image — vom Host/Compose gemountet |

Runtime-Konfiguration (DB, Qdrant, API-Keys) kommt aus `.env`, nicht aus dem Dockerfile.

## Siehe auch

- [`docs/docs/docker-compose.md`](../docker-compose.md) — Service `api`, Build-Kontext
- [`docs/docs/docker-compose.prod.md`](../docker-compose.prod.md) — Produktions-Compose
- [`docs/docs/backend/app/main.md`](../backend/app/main.md) — FastAPI-Einstieg (noch anzulegen)
- [`docs/docs/backend/app/config.md`](../backend/app/config.md) — Env-Variablen

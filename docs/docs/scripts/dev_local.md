# `scripts/dev_local.sh`

**Quellpfad:** `scripts/dev_local.sh`

## Zweck und logischer Aufbau

Startet eine **zweite native Dev-Instanz** auf Port 8090 (ohne Docker): lädt/startet Qdrant-Binary lokal, optional erstes DB-Seed, dann Uvicorn-API. Unterkommandos: `start` (Default), `stop`, `status`. Daten liegen unter `data-dev/` (SQLite, Qdrant-Storage, PIDs, Logs).

Lesereihenfolge: Pfad-/Port-Variablen → `.env.dev`-Bootstrap → `_ensure_qdrant_binary` / Port-Checks → `_start_qdrant` / `_start_api` → `_seed_if_empty` → `case` auf `$1`.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `.env.dev` oder Kopie aus `.env` / `.env.dev.example`; `curl`, `ss`, `nohup`; Qdrant Release v1.18.1; `scripts/seed_setup.py`
- **Wird genutzt von:** Entwickler parallel zur Docker-Instanz (:8088)
- **CLI:** `./scripts/dev_local.sh [start|stop|status]`
- **Daten:** `data-dev/support_kb.sqlite3`, `data-dev/qdrant_storage`, PID-Dateien in `data-dev/pids/`
- **HTTP:** API `http://127.0.0.1:${DEV_PORT}/api/health`, Qdrant `:${QDRANT_PORT}`

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `ROOT` | Shell | Repo-Root |
| `DEV_PORT` | Env/Default | `8090` |
| `QDRANT_PORT` | Env/Default | `6334` (abweichend von Standard 6333) |
| `TOOLS` | Pfad | `$ROOT/.tools` — Qdrant-Binary |
| `QDRANT_BIN` | Pfad | `$TOOLS/qdrant` |
| `QDRANT_STORAGE` | Pfad | `data-dev/qdrant_storage` |
| `PID_DIR` | Pfad | `data-dev/pids` |
| `API_PID` / `QDRANT_PID` | Pfad | PID-Dateien für Stop |

## Funktionen und Klassen

### `_ensure_qdrant_binary()`

**Beschreibung:** Lädt einmalig Qdrant-Tarball von GitHub (Arch `x86_64` oder `aarch64`), Version `1.18.1`, nach `$TOOLS`.

**Ablauf / lokale Variablen:** `qarch` — Rust-Target-Triple; `tmp` — temporäres `.tgz`.

---

### `_port_in_use()`

**Beschreibung:** Prüft via `ss -tln`, ob TCP-Port `$1` belegt ist.

---

### `_start_qdrant()`

**Beschreibung:** Überspringt Start wenn Port belegt; sonst `nohup` mit `QDRANT__SERVICE__HTTP_PORT` und `QDRANT__STORAGE__STORAGE_PATH`; wartet bis 30×0,5 s auf HTTP-Root.

**Aufrufer / Aufgerufene:** `_ensure_qdrant_binary`, schreibt `$QDRANT_PID`.

---

### `_start_api()`

**Beschreibung:** Bricht ab wenn `DEV_PORT` belegt; sourced `.env.dev`, setzt `APP_PORT`, startet `uvicorn app.main:app` mit `PYTHONPATH=backend`, Log `data-dev/api.log`, Health `/api/health`.

---

### `_seed_if_empty()`

**Beschreibung:** Nur wenn `data-dev/support_kb.sqlite3` fehlt: ruft `seed_setup.py --profile dev` mit `SEED_ADMIN_PASSWORD` (Default `DevLocal123!`) und `SEED_ADMIN_EMAIL` (Default `admin@example.com`).

---

### `_stop_one(pidfile, label)`

**Beschreibung:** Liest PID, `kill` wenn Prozess lebt, entfernt PID-Datei.

---

### Haupt-`case` auf `cmd="${1:-start}"`

**Beschreibung:** `start` → Qdrant, Seed, API; `stop` → API + Qdrant; `status` → Health + Qdrant-Root-Snippet; sonst Usage.

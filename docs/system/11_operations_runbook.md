# 11 — Operations-Runbook (Querschnitt)

**Stand:** 2026-06-03

---

## Schnellentscheidung

| Ziel | Befehl |
|---|---|
| **Erstinstallation** | `./install.sh` |
| **Setup/Wizard** | `./setup.sh` |
| **Docker starten** | `./scripts/start.sh` |
| **Docker stoppen** | `./scripts/stop.sh` |
| **Update (pull + rebuild)** | `./scripts/update.sh` |
| **Dev ohne Docker** | `./scripts/dev_local.sh start` |
| **Dev stoppen** | `./scripts/dev_local.sh stop` |
| **Health** | `curl http://127.0.0.1:8088/api/health` (Docker) oder `:8090` (dev_local) |

Ausführlich: [`docs/11_setup_and_operations.md`](../11_setup_and_operations.md), [`DEPLOY.md`](../DEPLOY.md)

---

## Typische Flows

### Neuer Entwickler (WSL, schnell testen)

```bash
git clone … && cd SUP_QA_Helper
cp .env.dev.example .env.dev   # OPENAI_API_KEY setzen
./scripts/dev_local.sh start
# → http://localhost:8090
```

Seed optional: `PYTHONPATH=backend python scripts/seed_setup.py` (siehe Spiegel `scripts/seed_setup.md`)

### Produktion (Ubuntu + Docker)

```bash
./setup.sh --non-interactive …
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
./scripts/update.sh   # später: git pull + rebuild
```

### Nach Code-Änderung (Dev)

```bash
./scripts/dev_local.sh stop && ./scripts/dev_local.sh start
```

---

## Daten & Backups

| Pfad | Inhalt |
|---|---|
| `./data/` (Docker) | SQLite + uploads |
| `./data-dev/` (dev_local) | Isolierte Dev-Daten |
| Qdrant Volume / `data-dev/qdrant_storage` | Vektoren |

Backup = SQLite-Datei + Qdrant-Snapshot/Volume + `data/uploads/`.

---

## Logs

| Modus | Log |
|---|---|
| dev_local | `tail -f data-dev/api.log` |
| Docker | `docker compose logs -f api` |

---

## Skript-Spiegel (Detail)

Jedes Skript: `docs/docs/scripts/<name>.md` oder Root `install.md`, `setup.md`.

---

## Betroffene Spiegel-Dateien

`install.md`, `setup.md`, `scripts/*.md`, `docker-compose*.md`, `docs/11_setup_and_operations.md`

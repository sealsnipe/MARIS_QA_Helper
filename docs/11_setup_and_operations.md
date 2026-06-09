# 11 — Setup & Betrieb

**Stand:** 2026-06-03 · **Status:** verbindlich für MVP + Dev lokal

Entwicklung **und** Deployment auf **Ubuntu** (Dev-Prod-Parität). Der Coding-Agent arbeitet in
Ubuntu (WSL2); das Projekt liegt im Linux-Dateisystem (`~/projects/SUP_QA_Helper`), nicht unter
`/mnt/...`.

---

## 1. Entwicklungsumgebung (Ubuntu)
- Projekt im Linux-FS: `~/projects/SUP_QA_Helper` (native Performance, korrekte Zeilenenden/Case).
- **Schnell ohne Docker:** `./scripts/dev_local.sh start` → API **8090**, Qdrant **6334**, Daten in `./data-dev/` (siehe `.env.dev.example`).
- **Docker:** Engine + Compose — Port **8088** (Standard-Stack).
- `.gitattributes` erzwingt LF; Imports/Dateinamen **case-genau**.

Runbook-Querschnitt: [`system/11_operations_runbook.md`](../system/11_operations_runbook.md)

## 2. Voraussetzungen
- Docker + Docker Compose (Plugin v2), gültiger OpenAI API-Key.
- **Automatisch:** `./setup.sh` prüft Docker und kann auf Ubuntu/Debian per apt installieren
  (`scripts/docker_preflight.py --install`, im Wizard interaktiv oder `--install-docker`).
- **WSL:** Docker Desktop WSL-Integration (Dev) oder Engine-Install im Wizard.
- (Für Tests ohne Container: Python 3.12.)

**Optional für beste Embed-Bildqualität (Vision-OCR):** `poppler-utils` (stellt `pdfimages` bereit). In Docker (Backend-Image) automatisch installiert. Lokal/Dev: `apt-get install -y poppler-utils`. Ohne: pypdf-Fallback (funktioniert, aber resampled Qualität).

## 3. Environment-Variablen
`.env` aus `.env.example`. Pflicht ohne sinnvollen Default markiert.

| Variable | Beispiel/Default | Pflicht | Zweck |
|---|---|---|---|
| `APP_HOST` | `0.0.0.0` | | Bind-Host |
| `APP_PORT` | `8088` | | Port |
| `SESSION_SECRET` | `<langer-zufall>` | ✅ | Cookie-Signatur (Fail-fast) |
| `DATABASE_URL` | `sqlite:///./data/support_kb.sqlite3` | | SQLite |
| `QDRANT_URL` | `http://qdrant:6333` | | Qdrant |
| `COLLECTION_PREFIX` | `kb_` | | Prefix → `kb_{customer_id}` |
| `OPENAI_API_KEY` | `sk-...` | ✅ | OpenAI (Fail-fast) |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | | API-Basis |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | | Embeddings |
| `EMBEDDING_DIM` | `1536` | | Vektordimension (muss zur Collection passen!) |
| `CHAT_MODEL` | `gpt-4.1-mini` | | Chat (Fallback: `gpt-4o-mini`) |
| `LLM_AUTH_MODE` | `chatgpt_oauth` | | `api_key` oder `chatgpt_oauth` |
| `SESSION_COOKIE_SECURE` | `false` | | `true` hinter HTTPS/TLS-Proxy |
| `TOP_K_DEFAULT` | `4` | | Treffer pro Suche |
| `MIN_SCORE_DEFAULT` | `0.25` | | Score-Schwelle (empirisch tunen) |
| `MAX_TOOL_ROUNDS` | `4` | | Agent-Loop-Begrenzung |
| `MAX_UPLOAD_MB` | `30` | | Upload-Limit |
| `ALLOWED_EXTENSIONS` | `.txt,.md,.pdf,.docx` | | erlaubte Dateitypen |

`SESSION_SECRET` erzeugen: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

> **dim/Collection:** `EMBEDDING_DIM` muss zur Collection passen. Modellwechsel mit anderer
> Dimension → Collections neu anlegen.

## 4. docker-compose.yml (Soll)
```yaml
services:
  api:
    build: ./backend
    ports: ["8088:8088"]
    env_file: [.env]
    volumes: ["./data:/app/data"]     # SQLite + uploads/
    depends_on: [qdrant]
    restart: unless-stopped
  qdrant:
    image: qdrant/qdrant:latest
    ports: ["6333:6333"]
    volumes: ["qdrant_storage:/qdrant/storage"]
    restart: unless-stopped
volumes:
  qdrant_storage:
```
Uvicorn mit **einem** Worker (SQLite-Locking), WAL aktiv.

## 5. Erststart (Ubuntu)

**Interaktiv (empfohlen):** Embedding-Key + Chat-Auth (API oder OAuth) in einem Durchlauf:

```bash
cd ~/projects/SUP_QA_Helper
./setup.sh
# oder: python3 scripts/setup.py
```

Ablauf:
1. Voraussetzungen prüfen (Python, Docker)
2. **Einsatzumgebung:** Entwicklung oder Produktion (HTTPS)
3. **Start-Art:** Docker Compose oder nur `.env` (uvicorn lokal)
4. **OpenAI API-Key** für Embeddings (immer Pflicht)
5. **Chat-Modus:** API-Key (Produktion) oder ChatGPT OAuth (Dev/WSL, Browser-Login)
6. `.env` schreiben (`SESSION_COOKIE_SECURE`, `QDRANT_URL` passend zur Wahl)
7. Optional: `docker compose` mit passendem Overlay starten
   - Produktion: `-f docker-compose.prod.yml`
   - OAuth in Docker: `-f docker-compose.oauth.yml` + `OAUTH_AUTH_HOST_PATH`

**Manuell:**

```bash
cd ~/projects/SUP_QA_Helper
cp .env.example .env
python3 scripts/setup_env.py          # nur OPENAI_API_KEY + SESSION_SECRET
python3 scripts/login_chat_oauth.py   # nur bei OAuth-Chat
docker compose up --build
curl http://localhost:8088/api/health      # -> {"ok":true}
```

## 6. Seed (Kunden, Nutzer, KB)
```bash
# Erst-Setup legt Kunden + Admin an (./setup.sh / seed_setup.py)
docker compose exec api python scripts/seed_kb.py   # optional: KB je Produktionskunde
docker compose exec -T -e SEED_ADMIN_PASSWORD='…' api \
  python scripts/seed_setup.py --profile prod --email admin@example.com
```
- Seed-Scripts idempotent. Kunden: `global`, `bg-ludwigshafen`, `bg-frankfurt`, `detmold-lippe`, `kkrr`.

## 7. Deployment auf Ubuntu-Server (Runbook)
```bash
# Voraussetzung: Docker Engine + Compose-Plugin auf dem Server
git clone <repo> ~/SUP_QA_Helper && cd ~/SUP_QA_Helper
python3 scripts/setup.py --non-interactive \
  --openai-key "$OPENAI_API_KEY" \
  --llm-auth-mode api_key \
  --no-start
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
# Seed wie in §6
```
- **Autostart:** `restart: unless-stopped` (compose) oder `systemd`-Unit, die `docker compose up -d` fährt.
- **TLS/Domain (empfohlen produktiv):** Reverse-Proxy (Caddy/nginx) vor Port 8088; dann
  `SESSION_COOKIE_SECURE=true` (bereits in `docker-compose.prod.yml`).
- **OAuth in Docker (Dev):** `docker-compose.oauth.yml` mit `OAUTH_AUTH_HOST_PATH` — siehe Root-`README.md`.
- Da Dev in Ubuntu erfolgt, ist der Server-Deploy im Kern derselbe `docker compose up`.

## 8. Betrieb / häufige Aufgaben
| Aufgabe | Vorgehen |
|---|---|
| Logs | `docker compose logs -f api` |
| Neustart | `docker compose restart api` |
| KB **eines Kunden** zurücksetzen | Dokumente löschen (UI) **oder** Collection `kb_{cid}` droppen + zugehörige SQLite-Rows |
| Alles zurücksetzen | `docker compose down -v` **und** SQLite-Datei + `data/uploads/` leeren, dann neu seeden |
| Nutzer/Kunde hinzufügen | `seed_customers.py` / `seed_users.py` |
| Schwelle tunen | `MIN_SCORE_DEFAULT` anpassen, `api` neu starten |

> **Konsistenz:** Qdrant-Volume und SQLite zusammen zurücksetzen (sonst Drift: Points ohne Rows).

## 9. Vor Inbetriebnahme — Go-Live-Checkliste
1. **OpenAI-Key** besorgen + Billing/Guthaben (`platform.openai.com`), in `.env`.
2. **`SESSION_SECRET`** generieren + setzen.
3. **Modellverfügbarkeit** prüfen; Fallback `CHAT_MODEL=gpt-4o-mini`.
4. **Smoke** mit echtem Key (nach M5): Seed-KB, echte Frage, Quellen prüfen.
5. **HTTPS/`SESSION_COOKIE_SECURE=true`** bei Server-Betrieb hinter TLS (`docker-compose.prod.yml`).

> Produktionsreife Secrets-Behandlung (Manager statt `.env`, Rotation) ist Roadmap (`12`, Auth & Compliance).

## 10. Troubleshooting
| Symptom | Ursache / Lösung |
|---|---|
| Start bricht mit Config-Fehler ab | `OPENAI_API_KEY`/`SESSION_SECRET` fehlt |
| Chat 502 | Key ungültig/kein Netz/Rate-Limit |
| Upload 502 `vector_store_failed` | Qdrant nicht erreichbar |
| Upload 422 `extraction_failed` | leeres/kaputtes PDF/DOCX (erwartet) → Dokument `failed` |
| Upload 400/413 | falscher Typ / über 30 MB |
| Suche findet nichts | `MIN_SCORE_DEFAULT` zu hoch; oder falscher aktiver Kunde; oder dim/Collection-Mismatch |
| 403 forbidden_customer | Nutzer ist diesem Kunden nicht zugeordnet (Seed prüfen) |
| Login klappt nie | Nutzer/Kunde nicht geseedet; E-Mail-Case (lower) |

## 11. Sicherheits-Hinweise Betrieb
- `.env` nie committen (`.gitignore`). Produktiv TLS vorschalten, `SESSION_COOKIE_SECURE=true`.
- Key-Rotation: `OPENAI_API_KEY`/`SESSION_SECRET` rotierbar (invalidiert Sessions — gewollt).
- `data/uploads/` enthält Originaldateien pro Kunde — Backup/Aufbewahrung beachten.

# 11 — Setup & Betrieb

**Stand:** 2026-06-02 · **Status:** verbindlich für MVP

Entwicklung **und** Deployment auf **Ubuntu** (Dev-Prod-Parität). Der Coding-Agent arbeitet in
Ubuntu (WSL2); das Projekt liegt im Linux-Dateisystem (`~/projects/SUP_QA_Helper`), nicht unter
`/mnt/...`.

---

## 1. Entwicklungsumgebung (Ubuntu)
- Projekt im Linux-FS: `~/projects/SUP_QA_Helper` (native Performance, korrekte Zeilenenden/Case).
- Docker Engine + Compose-Plugin (oder Docker Desktop mit WSL2-Backend).
- `.gitattributes` erzwingt LF (`* text=auto eol=lf`); Imports/Dateinamen **case-genau**
  (Linux ist case-sensitiv).
- Optional: VS Code Remote-WSL für Editor-Komfort.

## 2. Voraussetzungen
- Docker + Docker Compose, gültiger OpenAI API-Key.
- (Für Tests ohne Container: Python 3.12.)

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
| `TOP_K_DEFAULT` | `6` | | Treffer pro Suche |
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
2. `.env` aus `.env.example` anlegen
3. **OpenAI API-Key** für Embeddings (immer Pflicht, Platform-Billing)
4. **Chat-Modus wählen:**
   - **API-Key** — gleicher Key für Chat (`LLM_AUTH_MODE=api_key`, für Produktion/Docker)
   - **ChatGPT OAuth** — Browser-Login mit Einmalcode (`LLM_AUTH_MODE=chatgpt_oauth`, Dev/WSL)
5. Optional: `docker compose up --build -d`

**Manuell:**

```bash
cd ~/projects/SUP_QA_Helper
cp .env.example .env
python3 scripts/setup_env.py          # nur OPENAI_API_KEY + SESSION_SECRET
python3 scripts/login_chat_oauth.py   # nur bei OAuth-Chat
docker compose up --build
curl http://localhost:8088/api/health      # -> {"ok":true}
```

## 6. Seed (Kunden, Nutzer, Demo-Wissen)
```bash
docker compose exec api python scripts/seed_customers.py            # acme, globex
docker compose exec api python scripts/seed_users.py \
  --email sven@example.com --password 'GeheimesPW!' --customers acme,globex
docker compose exec api python scripts/seed_users.py \
  --email anna@example.com --password 'GeheimesPW!' --customers globex
docker compose exec api python scripts/seed_kb.py                   # Demo-Wissen je Kunde
```
- Alle Seed-Scripts idempotent. Demo-Wissen pro Kunde **deutlich unterschiedlich**, damit Isolation
  sichtbar ist (z. B. `acme`: VPN-Runbook; `globex`: Firewall-FAQ).

## 7. Deployment auf Ubuntu-Server (Runbook)
```bash
# Voraussetzung: Docker Engine + Compose-Plugin auf dem Server
git clone <repo> ~/SUP_QA_Helper && cd ~/SUP_QA_Helper
cp .env.example .env       # OPENAI_API_KEY, SESSION_SECRET setzen
docker compose up -d --build
# Seed wie in §6
```
- **Autostart:** `restart: unless-stopped` (compose) oder `systemd`-Unit, die `docker compose up -d` fährt.
- **TLS/Domain (empfohlen produktiv):** Reverse-Proxy (Caddy/nginx) vor Port 8088, dann
  `secure`-Cookie aktivieren. Firewall: nur Proxy-Ports (80/443) öffnen.
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
5. **HTTPS/`secure`-Cookie** bei Server-Betrieb hinter TLS.

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
- `.env` nie committen (`.gitignore`). Produktiv TLS vorschalten, `secure`-Cookie.
- Key-Rotation: `OPENAI_API_KEY`/`SESSION_SECRET` rotierbar (invalidiert Sessions — gewollt).
- `data/uploads/` enthält Originaldateien pro Kunde — Backup/Aufbewahrung beachten.

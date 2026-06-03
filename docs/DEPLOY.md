# Deploy — MARIS Q/A Helper

Anleitung für **Erst-Deploy** und **Updates** auf Ubuntu/WSL.  
**Keine Secrets im Git** — API-Key, OAuth und Passwörter werden **auf der Zielmaschine** im Setup-Wizard eingegeben.

Repo: https://github.com/sealsnipe/MARIS_QA_Helper

---

## Erst-Deploy (Ziel-WSL, interaktiv)

```bash
git clone https://github.com/sealsnipe/MARIS_QA_Helper.git ~/projects/SUP_QA_Helper
cd ~/projects/SUP_QA_Helper
./setup.sh
```

Der Wizard führt durch:

1. **Docker** — prüfen, Version validieren, bei Bedarf installieren (apt, sudo)  
2. **Dev vs. Prod** — Prod setzt `SESSION_COOKIE_SECURE=true`  
3. **Embedding API-Key** — interaktiv (Platform OpenAI, `sk-...`)  
4. **Chat-Auth** — API-Key (Prod) oder OAuth mit Browser-Login (Dev)  
5. **Docker Compose starten** — Prod: `docker-compose.prod.yml`

Health:

```bash
curl -s http://127.0.0.1:8088/api/health
# {"ok":true}
```

### Produktions-Seed (Passwort **nicht** im Repo)

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api \
  python scripts/seed_production.py
# Passwort interaktiv oder: SEED_ADMIN_PASSWORD=... (nur lokal, nicht committen)
```

Standard-Admin-E-Mail: `matthias.schindler@maris-healthcare.de` (überschreibbar mit `--email`).

Browser: http://127.0.0.1:8088 → Login → Kunde wählen → Chat/KB testen.

### HTTPS (später)

Reverse-Proxy (Caddy/nginx) vor Port 8088. `SESSION_COOKIE_SECURE=true` ist in Prod-Compose gesetzt.

---

## Cursor-Agent Prompt (Copy-Paste)

```text
Deploy MARIS Q/A Helper from https://github.com/sealsnipe/MARIS_QA_Helper
Path: ~/projects/SUP_QA_Helper (Linux filesystem, not /mnt/c).

1. git clone + cd
2. Run ./setup.sh INTERACTIVELY (user enters OpenAI key + auth on this machine)
3. Choose: Production + Docker
4. Verify: curl http://127.0.0.1:8088/api/health
5. docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api \
     python scripts/seed_production.py
   (admin password: ask user or SEED_ADMIN_PASSWORD env — never commit)
6. Browser smoke: login, customer, chat

Do NOT put API keys or passwords in git or in command history files.
Docs: docs/DEPLOY.md, README.md
Update later: ./scripts/update.sh
```

---

## Updates (du entwickelst hier, Server läuft dort)

Auf der **Deploy-Maschine**:

```bash
cd ~/projects/SUP_QA_Helper
./scripts/update.sh
```

Das macht:

1. `git pull --ff-only`
2. `docker compose … up -d --build` (Prod-Overlay)
3. Health-Check

**Daten bleiben erhalten:** SQLite + Uploads in `./data/`, Qdrant im Docker-Volume `qdrant_storage`.

| Was | Verhalten beim Update |
|---|---|
| Code / UI / Agent | Neu gebaut via `--build` |
| `.env` | **Bleibt** (liegt lokal, nicht im Git) |
| KB / Chats / Nutzer | **Bleiben** in `./data/` |
| Qdrant-Vektoren | **Bleiben** im Volume |

Nach Schema-Änderungen startet die API `init_db()` idempotent beim Container-Start.

**Workflow:**

```text
[Dev-Maschine]  commit + push → GitHub
[Deploy-Maschine]  ./scripts/update.sh
```

Bei Konflikten: auf Deploy-Maschine keine lokalen Code-Änderungen — nur `.env` und `data/` sind lokal.

---

## Docker-Versionen (Pflicht)

| Komponente | Minimum |
|---|---|
| Docker Engine | 20.10 |
| docker compose (Plugin) | 2.20 |

Prüfen: `python3 scripts/docker_preflight.py --check`  
Zu alt → Setup bricht ab (Upgrade via `--install` / apt).

Bereits installiert und Version ok → Installation wird übersprungen.

---

## WSL-Hinweise

- **Docker Desktop:** WSL-Integration für diese Distro aktivieren, dann erneut `./setup.sh`
- **Ohne Desktop:** Wizard bietet Engine-Install in WSL (sudo)
- Nach `usermod -aG docker`: Terminal neu öffnen oder `newgrp docker`

---

## Troubleshooting

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f api
docker compose ps
python3 scripts/setup_env.py --check-only
```

| Problem | Lösung |
|---|---|
| Docker daemon | WSL: Desktop starten / `sudo service docker start` |
| 403 Login | Seed ausführen, Kunde in Session wählen |
| Chat 502 | `.env` OPENAI_API_KEY prüfen |
| OAuth Dev | `python3 scripts/login_chat_oauth.py` |

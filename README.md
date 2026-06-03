# MARIS Q/A Helper

Selbst gehosteter Support-Chatbot mit **mandanten-isolierter** Wissensdatenbank (RAG), Login, Datei-Upload und belegten Antworten.

## Schnellstart

```bash
git clone https://github.com/sealsnipe/MARIS_QA_Helper.git ~/projects/SUP_QA_Helper
cd ~/projects/SUP_QA_Helper
./install.sh
```

**Frisches Ubuntu:** `./install.sh` installiert Pakete + Docker, dann Credentials-Wizard.  
**Docker schon vorhanden:** `./setup.sh`

**Credentials nur auf der Zielmaschine** — API-Key und Auth werden interaktiv abgefragt (nichts ins Git).

Deploy & Updates: [`docs/DEPLOY.md`](docs/DEPLOY.md)

Der Setup-Wizard:
1. prüft **Python** und **Docker** (optional Installation per apt auf Ubuntu/Debian)
2. fragt **Dev vs. Produktion** (setzt `SESSION_COOKIE_SECURE`)
2. wählt **Docker oder lokal** (setzt `QDRANT_URL`)
3. fragt den **OpenAI API-Key für Embeddings**
4. lässt **Chat-Auth wählen** (API-Key oder OAuth mit Browser-Login)
5. startet optional den passenden **Docker-Stack** (inkl. Prod-/OAuth-Overlay)

Health-Check: `curl http://127.0.0.1:8088/api/health` → `{"ok":true}`

### Demo-Daten

```bash
docker compose exec api python scripts/seed_setup.py --profile dev
# oder Demo-Wissen: docker compose exec api python scripts/seed_kb.py
```

Login mit dem im Setup angelegten Admin-Nutzer (E-Mail + Passwort beim `./setup.sh`).

## Entwicklung (ohne Docker)

```bash
cp .env.example .env
python3 scripts/setup.py --no-start
# Qdrant lokal (Binary oder Docker nur qdrant)
cd backend && PYTHONPATH=. uvicorn app.main:app --reload --port 8088
```

Qdrant-URL in `.env` für lokalen Betrieb: `QDRANT_URL=http://127.0.0.1:6333`

## Tests

```bash
cd backend && PYTHONPATH=. pytest -q
```

Tenant-Isolation (Pflicht): `pytest app/tests/test_tenant_isolation.py -q`

## Produktion (Ubuntu + Docker)

Empfohlen hinter TLS-Reverse-Proxy (Caddy/nginx):

```bash
cp .env.example .env
python3 scripts/setup.py --non-interactive \
  --openai-key "$OPENAI_API_KEY" \
  --llm-auth-mode api_key \
  --no-start

docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

`docker-compose.prod.yml` setzt `SESSION_COOKIE_SECURE=true` und `LLM_AUTH_MODE=api_key`.

**OAuth in Docker** (selten, eher Dev):

```bash
OAUTH_AUTH_HOST_PATH=$HOME/.oauth_codex/auth.json \
  docker compose -f docker-compose.yml -f docker-compose.oauth.yml up -d
```

### Caddy (Beispiel)

```caddy
maris-helper.example.com {
    reverse_proxy 127.0.0.1:8088
}
```

Mit TLS vor dem Proxy muss `SESSION_COOKIE_SECURE=true` gesetzt sein (siehe `docker-compose.prod.yml`).

## Projektstruktur

| Pfad | Inhalt |
|---|---|
| `backend/app/` | FastAPI, Agent, RAG, UI |
| `scripts/` | Setup, Seed, OAuth-Login, Smoke-Tests |
| `docs/` | Architektur, API, Betrieb |
| `docker-compose.yml` | API + Qdrant |

## Dokumentation

Ausführliches Runbook: [`docs/11_setup_and_operations.md`](docs/11_setup_and_operations.md)  
Implementierungsplan: [`docs/09_implementation_plan.md`](docs/09_implementation_plan.md)

## Secrets

Niemals `.env` oder OAuth-Token committen. `.env.example` enthält Platzhalter.

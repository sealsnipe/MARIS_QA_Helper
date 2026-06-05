# 12 — Integration API (externe Agenten)

**Stand:** 2026-06-04  
**Ebene:** Querschnitt

---

## Zweck

Schlanke REST-Schnittstelle für **Frage rein, Antwort raus** — damit externe Agenten (Cursor, n8n, CI, eigene Tools) den MARIS Q/A Helper als Wissens-Tool nutzen können, ohne Browser-Session.

Kein WebSocket im MVP: sync JSON reicht für Tool-Calls.

---

## Endpoint

| Methode | Pfad | Auth |
|---|---|---|
| `POST` | `/api/v1/ask` | `Authorization: Bearer <INTEGRATION_API_TOKEN>` |
| `POST` | `/api/v1/knowledge-content` | `Authorization: Bearer <INTEGRATION_API_TOKEN>` |

OpenAPI: `http://localhost:8088/docs` (Tag **Integration**).

---

## Knowledge Center Ingest

Worker liefern Content-Vorschläge an das Knowledge Center (Staging vor KB-Review):

```json
{
  "host_code": "agent-alpha",
  "items": [
    {
      "title": "Titel",
      "summary": "Kurztext",
      "content": "Volltext (min. 20 Zeichen)",
      "keywords": ["a", "b"],
      "source_ref": "https://…",
      "customer_id": "bg-frankfurt",
      "external_id": "dedup-key"
    }
  ]
}
```

- `host_code` muss einer aktiven Source entsprechen (Admin: Tools → Knowledge Center → Sources).
- `customer_id` optional — Vorschlag für Review; finale KB-Zuordnung wählt der Nutzer im Content Dashboard.
- Duplikat `(source, external_id)`: bestehender **pending**-Eintrag wird aktualisiert.

Antwort: `{ "created", "updated", "skipped", "errors" }`.

---

## Konfiguration (`.env`)

| Variable | Default | Bedeutung |
|---|---|---|
| `INTEGRATION_API_TOKEN` | *(leer)* | Geheimer Token; leer = Endpoint deaktiviert (`503`) |
| `INTEGRATION_USER_EMAIL` | `integration@internal` | DB-User für Chat-Persistenz |

**Service-User anlegen:**

```bash
python3 scripts/seed_users.py --defaults
```

Der User `integration@internal` wird mit allen Produktiv-Mandanten verknüpft (nur für Chat-Ownership; Suche bleibt auf den angefragten `customer_id` begrenzt).

**Token erzeugen:**

```bash
openssl rand -hex 32
```

In `.env` eintragen, dann `./scripts/restart.sh`.

---

## Request / Response

**Request:**

```json
{
  "question": "Wie sind die Öffnungszeiten?",
  "customer_id": "bg-frankfurt",
  "chat_id": "optional-uuid-für-follow-up",
  "top_k": 4
}
```

**Response `200`:**

```json
{
  "answer": "Die Öffnungszeiten sind … [1]",
  "sources": [
    {
      "n": 1,
      "document_id": "…",
      "title": "FAQ",
      "chunk_index": 2,
      "score": 0.81
    }
  ],
  "no_context": false,
  "chat_id": "uuid",
  "customer_id": "bg-frankfurt"
}
```

---

## curl-Beispiel

```bash
curl -sS http://127.0.0.1:8088/api/v1/ask \
  -H "Authorization: Bearer $INTEGRATION_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question":"Öffnungszeiten?","customer_id":"bg-frankfurt"}'
```

Follow-up (gleicher Chat):

```bash
curl -sS http://127.0.0.1:8088/api/v1/ask \
  -H "Authorization: Bearer $INTEGRATION_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question":"Und am Wochenende?","customer_id":"bg-frankfurt","chat_id":"<chat_id-aus-erster-antwort>"}'
```

---

## Agent-Tool-Schema (OpenAI / Cursor)

```json
{
  "name": "ask_maris_qa",
  "description": "Fragt den MARIS Q/A Helper Wissensbot für einen Mandanten.",
  "parameters": {
    "type": "object",
    "properties": {
      "question": { "type": "string" },
      "customer_id": {
        "type": "string",
        "description": "Mandanten-Slug, z.B. bg-frankfurt"
      },
      "chat_id": {
        "type": "string",
        "description": "Optional: Chat-ID für Follow-up-Fragen"
      }
    },
    "required": ["question", "customer_id"]
  }
}
```

Tool-Implementierung: HTTP POST auf `/api/v1/ask` mit Bearer-Header; `chat_id` aus der Antwort für Folgefragen merken.

---

## Ablauf (intern)

```text
POST /api/v1/ask + Bearer
  → integration_auth: Token prüfen (timing-safe)
  → integration_user aus DB laden
  → customer_id validieren (existiert, aktiv)
  → Chat-Session laden/erzeugen (chats.py)
  → agent.run(customer_id, question, scope=[customer_id])
  → Messages persistieren
  → JSON { answer, sources, no_context, chat_id, customer_id }
```

Gleiche RAG-Pipeline wie `POST /api/chat` — nur andere Auth und expliziter Mandant im Body.

---

## Fehlercodes

| HTTP | `error` | Ursache |
|---|---|---|
| 401 | `invalid_token` | Fehlender/falscher Bearer |
| 400 | `empty_question` | Leere Frage nach Trim |
| 403 | `forbidden_customer` | Unbekannter/inaktiver Mandant |
| 404 | `not_found` | Unbekannte `chat_id` |
| 503 | `integration_disabled` | `INTEGRATION_API_TOKEN` nicht gesetzt |
| 503 | `integration_user_missing` | Service-User fehlt/inaktiv |
| 502 | `llm_failed` | LLM/Upstream-Fehler |

---

## Sicherheit

- Token **nur** im `Authorization`-Header, nie als Query-Parameter.
- Endpoint ist fail-closed ohne Token.
- Mandanten-Suche auf den angefragten `customer_id` begrenzt (kein Cross-Tenant über Integration-User-Zuordnungen).
- Rate-Limiting: nicht im MVP (später Reverse-Proxy).

---

## Abgrenzung zu `/api/chat`

| | Web-UI `/api/chat` | Integration `/api/v1/ask` |
|---|---|---|
| Auth | Session-Cookie | Bearer-Token |
| Mandant | Session | JSON-Body |
| Chat-Owner | Eingeloggter User | Integration-Service-User |

---

## Betroffene Dateien

- `backend/app/integration_auth.py` — Bearer-Auth
- `backend/app/integration_routes.py` — Endpoint
- `backend/app/config.py` — Settings
- `backend/app/tests/test_integration_api.py` — Tests

Spiegel-Spec: [`docs/05_api_specification.md`](../05_api_specification.md) §3.12

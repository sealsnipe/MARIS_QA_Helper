# `backend/app/integration_routes.py`

**Quellpfad:** `backend/app/integration_routes.py`

## Zweck und logischer Aufbau

Separat gemounteter Router (`main.py`: `include_router(integration_router)`) für die externe Integrations-API (`/api/v1`).

- `POST /api/v1/ask`: Frage + optional chat + customer_id (aus Body, nicht Session); nutzt `get_integration_user` + scoped Agent-Run + Chat-Session.
- `POST /api/v1/knowledge-content`: Batch-Ingest von Vorschlägen (host_code + items) → `knowledge_center.ingest_knowledge_contents`.

Eigener Auth (Bearer), eigener Error-Handling-Pfad. Gute Modulgrenze zu `routes.py`.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.agent.run as run_agent`
  - `app.chats` (create/get_session, add_message, Chat*Error)
  - `app.customers` (get_customer, is_customer_active)
  - `app.db.get_db`
  - `app.integration_auth.get_integration_user`
  - `app.knowledge_center` (KnowledgeCenterError, ingest_knowledge_contents)
  - `app.models`
  - `app.retrieval.filter_sources_by_answer_citations`
- **Wird genutzt von:** `main.py` (Mount), externe Clients (Cursor, n8n, ...); Tests `test_integration_api.py`
- **HTTP / UI:** Nur JSON v1; keine HTML.
- **Daten:** chat_sessions/messages (für integration user), knowledge_contents, customers (active check).

## Konstanten, Typen und Modulebene

Pydantic Models: `IntegrationAskRequest`, `IntegrationKnowledgeContentItem`, `IntegrationKnowledgeContentRequest`.

## Funktionen und Klassen

### `_require_active_customer(db, customer_id) -> Customer | JSONResponse`

Prüft exist + active → sonst 403 JSON (früh, vor Agent).

### `api_v1_ask(...)`

- Validierung question.
- Customer-Check.
- Chat-Session (create oder get mit user+customer).
- `run_agent(customer.id, question, scope_customer_ids=[customer.id])` (Isolation).
- Filter Sources, persist messages, return answer + sources + chat_id.

### `api_v1_knowledge_content(...)`

Delegiert an `ingest_knowledge_contents`; fängt `KnowledgeCenterError` zu JSON.

Router: `APIRouter(tags=["Integration"])`.

# `scripts/seed_knowledge_center_demo.py`

**Quellpfad:** `scripts/seed_knowledge_center_demo.py`

## Zweck

Demo-Seed für Knowledge Center: legt 2 Sources an (demo-agent, jira-sync), ingestet 4 Sample-Contents (mit/ohne customer_id, external_id). Für lokale Tests von KC-Dashboard, Adopt, Integration-API.

Wird manuell ausgeführt (nach DB/Qdrant up).

## Ablauf (kurz)

1. PYTHONPATH + imports (app.knowledge_center, db).
2. Für jede DEMO_SOURCE: create wenn nicht exist.
3. ingest für demo-agent (Items 0-2), jira-sync (Item 3).
4. Print Status + Hinweise auf UI + curl-Beispiel (mit Token).

## Konfiguration / Parameter

- Env: `INTEGRATION_API_TOKEN` (für curl-Hinweis).
- DB via `DATABASE_URL` (default sqlite data/).
- Keine Netz-Calls.

## Siehe auch

- `docs/docs/backend/app/knowledge_center.md`
- `docs/docs/backend/app/tests/test_knowledge_center.md`
- `docs/docs/backend/app/integration_routes.md`
- `docs/system/12_integration_api.md`
- `scripts/seed_*.py` (andere Seeds)

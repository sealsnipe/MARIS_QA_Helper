# Code-Spiegel — Index

**Regelwerk:** [`docs/DOCUMENTATION_RULES.md`](../DOCUMENTATION_RULES.md)

```
<repo>/<pfad>/<datei>.<ext>  →  docs/docs/<pfad>/<datei>.md
```

**Sonderfall:** `app.js` und `app.css` → beide in [`backend/app/static/app.md`](./backend/app/static/app.md) (Basisname-Kollision).

---

## Hälfte A — Cursor (55 Dateien) ✓ (inkl. Post-MVP Module nach Review 2026-06)

| Spiegel | Quelle |
|---|---|
| [.env.dev.example.md](./.env.dev.example.md) | `.env.dev.example` |
| [.env.example.md](./.env.example.md) | `.env.example` |
| [backend/Dockerfile.md](./backend/Dockerfile.md) | `backend/Dockerfile` |
| [backend/app/__init__.md](./backend/app/__init__.md) | `backend/app/__init__.py` |
| [backend/app/agent.md](./backend/app/agent.md) | `backend/app/agent.py` |
| [backend/app/auth.md](./backend/app/auth.md) | `backend/app/auth.py` |
| [backend/app/chats.md](./backend/app/chats.md) | `backend/app/chats.py` |
| [backend/app/chunking.md](./backend/app/chunking.md) | `backend/app/chunking.py` |
| [backend/app/config.md](./backend/app/config.md) | `backend/app/config.py` |
| [backend/app/customers.md](./backend/app/customers.md) | `backend/app/customers.py` |
| [backend/app/db.md](./backend/app/db.md) | `backend/app/db.py` |
| [backend/app/embeddings.md](./backend/app/embeddings.md) | `backend/app/embeddings.py` |
| [backend/app/ingestion.md](./backend/app/ingestion.md) | `backend/app/ingestion.py` |
| [backend/app/llm.md](./backend/app/llm.md) | `backend/app/llm.py` |
| [backend/app/loaders/__init__.md](./backend/app/loaders/__init__.md) | `backend/app/loaders/__init__.py` |
| [backend/app/loaders/docx_loader.md](./backend/app/loaders/docx_loader.md) | `backend/app/loaders/docx_loader.py` |
| [backend/app/loaders/docx_content.md](./backend/app/loaders/docx_content.md) | `backend/app/loaders/docx_content.py` |
| [backend/app/loaders/image_inspect.md](./backend/app/loaders/image_inspect.md) | `backend/app/loaders/image_inspect.py` |
| [backend/app/loaders/vision_ocr.md](./backend/app/loaders/vision_ocr.md) | `backend/app/loaders/vision_ocr.py` |
| [backend/app/document_assets.md](./backend/app/document_assets.md) | `backend/app/document_assets.py` |
| [backend/app/document_fingerprints.md](./backend/app/document_fingerprints.md) | `backend/app/document_fingerprints.py` |
| [backend/app/document_merge.md](./backend/app/document_merge.md) | `backend/app/document_merge.py` |
| [backend/app/duplicates.md](./backend/app/duplicates.md) | `backend/app/duplicates.py` |
| [backend/app/integration_auth.md](./backend/app/integration_auth.md) | `backend/app/integration_auth.py` |
| [backend/app/integration_routes.md](./backend/app/integration_routes.md) | `backend/app/integration_routes.py` |
| [backend/app/knowledge_center.md](./backend/app/knowledge_center.md) | `backend/app/knowledge_center.py` |
| [backend/app/oauth_device_flow.md](./backend/app/oauth_device_flow.md) | `backend/app/oauth_device_flow.py` |
| [backend/app/roles_admin.md](./backend/app/roles_admin.md) | `backend/app/roles_admin.py` |
| [backend/app/secrets_admin.md](./backend/app/secrets_admin.md) | `backend/app/secrets_admin.py` |
| [backend/app/upload.md](./backend/app/upload.md) | `backend/app/upload.py` |
| [backend/app/loaders/errors.md](./backend/app/loaders/errors.md) | `backend/app/loaders/errors.py` |
| [backend/app/loaders/pdf_loader.md](./backend/app/loaders/pdf_loader.md) | `backend/app/loaders/pdf_loader.py` |
| [backend/app/loaders/text_loaders.md](./backend/app/loaders/text_loaders.md) | `backend/app/loaders/text_loaders.py` |
| [backend/app/main.md](./backend/app/main.md) | `backend/app/main.py` |
| [backend/app/models.md](./backend/app/models.md) | `backend/app/models.py` |
| [backend/app/prompts.md](./backend/app/prompts.md) | `backend/app/prompts.py` |
| [backend/app/qdrant_store.md](./backend/app/qdrant_store.md) | `backend/app/qdrant_store.py` |
| [backend/app/retrieval.md](./backend/app/retrieval.md) | `backend/app/retrieval.py` |
| [backend/app/routes.md](./backend/app/routes.md) | `backend/app/routes.py` |
| [backend/app/static/app.md](./backend/app/static/app.md) | `app.js` + `app.css` |
| [backend/app/static/brand-banner.md](./backend/app/static/brand-banner.md) | `brand-banner.svg` |
| [backend/app/static/brand-icon.md](./backend/app/static/brand-icon.md) | `brand-icon.svg` |
| [backend/app/static/brand-logo.md](./backend/app/static/brand-logo.md) | `brand-logo.svg` |
| [backend/app/static/vendor/marked.min.md](./backend/app/static/vendor/marked.min.md) | `marked.min.js` |
| [backend/app/static/vendor/purify.min.md](./backend/app/static/vendor/purify.min.md) | `purify.min.js` |
| [backend/app/system_prompts.md](./backend/app/system_prompts.md) | `backend/app/system_prompts.py` |
| [backend/app/templates/admin_knowledge.md](./backend/app/templates/admin_knowledge.md) | `admin_knowledge.html` |

| [backend/app/templates/admin_prompts.md](./backend/app/templates/admin_prompts.md) | `admin_prompts.html` |
| [backend/app/templates/admin_roles.md](./backend/app/templates/admin_roles.md) | `admin_roles.html` |
| [backend/app/templates/admin_users.md](./backend/app/templates/admin_users.md) | `admin_users.html` |
| [backend/app/templates/base.md](./backend/app/templates/base.md) | `base.html` |
| [backend/app/templates/chat.md](./backend/app/templates/chat.md) | `chat.html` |
| [backend/app/templates/customers.md](./backend/app/templates/customers.md) | `customers.html` |

| [backend/app/templates/kb.md](./backend/app/templates/kb.md) | `kb.html` |
| [backend/app/templates/layout.md](./backend/app/templates/layout.md) | `layout.html` |
| [backend/app/templates/login.md](./backend/app/templates/login.md) | `login.html` |
| [backend/app/templates/tools/bild_zu_text.md](./backend/app/templates/tools/bild_zu_text.md) | `tools/bild_zu_text.html` |
| [backend/app/templates/tools/knowledge_center_content.md](./backend/app/templates/tools/knowledge_center_content.md) | `tools/knowledge_center_content.html` |
| [backend/app/templates/tools/knowledge_center_sources.md](./backend/app/templates/tools/knowledge_center_sources.md) | `tools/knowledge_center_sources.html` |
| [backend/app/tenant.md](./backend/app/tenant.md) | `backend/app/tenant.py` |
| [backend/app/tests/__init__.md](./backend/app/tests/__init__.md) | `tests/__init__.py` |
| [backend/app/tests/conftest.md](./backend/app/tests/conftest.md) | `tests/conftest.py` |

## Root-Spiegel (nicht Teil des 93-Datei-Splits)

| Spiegel | Quelle |
|---|---|
| [README.md](./README.md) | `README.md` |

## Hälfte B — Grok (62 Dateien) ✓ (inkl. fehlende Spiegel nach Review 2026-06)

Vollständig dokumentiert (Subagenten B1–B4). Alle Einträge folgen Spiegelregel §2; install.md/setup.md/docker*.md/qdrant.md wurden ggf. an §6-Vorlage angepasst.

| Spiegel | Quelle |
|---|---|
| [test_admin.md](./backend/app/tests/test_admin.md) | `backend/app/tests/test_admin.py` |
| [test_admin_customers.md](./backend/app/tests/test_admin_customers.md) | `backend/app/tests/test_admin_customers.py` |
| [test_admin_users.md](./backend/app/tests/test_admin_users.md) | `backend/app/tests/test_admin_users.py` |
| [test_admin_keys.md](./backend/app/tests/test_admin_keys.md) | `backend/app/tests/test_admin_keys.py` |
| [test_admin_roles.md](./backend/app/tests/test_admin_roles.md) | `backend/app/tests/test_admin_roles.py` |
| [test_agent.md](./backend/app/tests/test_agent.md) | `backend/app/tests/test_agent.py` |
| [test_auth.md](./backend/app/tests/test_auth.md) | `backend/app/tests/test_auth.py` |
| [test_chats.md](./backend/app/tests/test_chats.md) | `backend/app/tests/test_chats.py` |
| [test_chunking.md](./backend/app/tests/test_chunking.md) | `backend/app/tests/test_chunking.py` |
| [test_customers.md](./backend/app/tests/test_customers.md) | `backend/app/tests/test_customers.py` |
| [test_documents_api.md](./backend/app/tests/test_documents_api.md) | `backend/app/tests/test_documents_api.py` |
| [test_docx_content.md](./backend/app/tests/test_docx_content.md) | `backend/app/tests/test_docx_content.py` |
| [test_duplicate_detection.md](./backend/app/tests/test_duplicate_detection.md) | `backend/app/tests/test_duplicate_detection.py` |
| [test_global_customer.md](./backend/app/tests/test_global_customer.md) | `backend/app/tests/test_global_customer.py` |
| [test_health.md](./backend/app/tests/test_health.md) | `backend/app/tests/test_health.py` |
| [test_ingestion.md](./backend/app/tests/test_ingestion.md) | `backend/app/tests/test_ingestion.py` |
| [test_image_inspect.md](./backend/app/tests/test_image_inspect.md) | `backend/app/tests/test_image_inspect.py` |
| [test_integration_api.md](./backend/app/tests/test_integration_api.md) | `backend/app/tests/test_integration_api.py` |
| [test_knowledge_center.md](./backend/app/tests/test_knowledge_center.md) | `backend/app/tests/test_knowledge_center.py` |
| [test_loaders.md](./backend/app/tests/test_loaders.md) | `backend/app/tests/test_loaders.py` |
| [test_retrieval.md](./backend/app/tests/test_retrieval.md) | `backend/app/tests/test_retrieval.py` |
| [test_selective_vision.md](./backend/app/tests/test_selective_vision.md) | `backend/app/tests/test_selective_vision.py` |
| [test_tenant_isolation.md](./backend/app/tests/test_tenant_isolation.md) | `backend/app/tests/test_tenant_isolation.py` |
| [test_upload_api.md](./backend/app/tests/test_upload_api.md) | `backend/app/tests/test_upload_api.py` |
| [test_vision_ocr.md](./backend/app/tests/test_vision_ocr.md) | `backend/app/tests/test_vision_ocr.py` |
| [test_document_fingerprints.md](./backend/app/tests/test_document_fingerprints.md) | `backend/app/tests/test_document_fingerprints.py` |
| [test_document_merge.md](./backend/app/tests/test_document_merge.md) | `backend/app/tests/test_document_merge.py` |
| [upload.md](./backend/app/upload.md) | `backend/app/upload.py` |
| [users_admin.md](./backend/app/users_admin.md) | `backend/app/users_admin.py` |
| [backend/pyproject.md](./backend/pyproject.md) | `backend/pyproject.toml` |
| [docker-compose.dev-local.md](./docker-compose.dev-local.md) | `docker-compose.dev-local.yml` |
| [docker-compose.oauth.md](./docker-compose.oauth.md) | `docker-compose.oauth.yml` |
| [docker-compose.prod.md](./docker-compose.prod.md) | `docker-compose.prod.yml` |
| [docker-compose.md](./docker-compose.md) | `docker-compose.yml` |
| [install.md](./install.md) | `install.sh` |
| [qdrant.md](./qdrant.md) | `qdrant.yaml` |
| [setup.md](./setup.md) | `setup.sh` |
| [compose_env.md](./scripts/compose_env.md) | `scripts/compose_env.sh` |
| [dev_local.md](./scripts/dev_local.md) | `scripts/dev_local.sh` |
| [docker_preflight.md](./scripts/docker_preflight.md) | `scripts/docker_preflight.py` |
| [import_codex_auth.md](./scripts/import_codex_auth.md) | `scripts/import_codex_auth.py` |
| [login_chat_oauth.md](./scripts/login_chat_oauth.md) | `scripts/login_chat_oauth.py` |
| [monitor_deploy.md](./scripts/monitor_deploy.md) | `scripts/monitor_deploy.sh` |
| [restart.md](./scripts/restart.md) | `scripts/restart.sh` |
| [seed_customers.md](./scripts/seed_customers.md) | `scripts/seed_customers.py` |
| [seed_data.md](./scripts/seed_data.md) | `scripts/seed_data.py` |
| [seed_kb.md](./scripts/seed_kb.md) | `scripts/seed_kb.py` |
| [seed_knowledge_center_demo.md](./scripts/seed_knowledge_center_demo.md) | `scripts/seed_knowledge_center_demo.py` |
| [seed_production.md](./scripts/seed_production.md) | `scripts/seed_production.py` |
| [seed_setup.md](./scripts/seed_setup.md) | `scripts/seed_setup.py` |
| [seed_users.md](./scripts/seed_users.md) | `scripts/seed_users.py` |
| [setup.md](./scripts/setup.md) | `scripts/setup.py` |
| [setup_env.md](./scripts/setup_env.md) | `scripts/setup_env.py` |
| [smoke_chat_oauth.md](./scripts/smoke_chat_oauth.md) | `scripts/smoke_chat_oauth.py` |
| [smoke_openai.md](./scripts/smoke_openai.md) | `scripts/smoke_openai.py` |
| [start.md](./scripts/start.md) | `scripts/start.sh` |
| [start_docker.md](./scripts/start_docker.md) | `scripts/start_docker.py` |
| [stop.md](./scripts/stop.md) | `scripts/stop.sh` |
| [update.md](./scripts/update.md) | `scripts/update.sh` |

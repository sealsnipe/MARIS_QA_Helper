# 10 — Test-Landschaft

**Stand:** 2026-06-03

---

## Ebenen

| Ebene | Ort | Zweck |
|---|---|---|
| Unit | `test_chunking`, `test_loaders`, `test_retrieval` | Isolierte Logik |
| Integration | `test_ingestion`, `test_agent`, `test_*_api` | FastAPI TestClient + Mocks |
| Isolation | **`test_tenant_isolation`** | Mandanten-Grenzen (Pflicht) |
| Admin | `test_admin*`, `test_customers` | Kunden/User/Rename |

Fixtures: `conftest.py` — DB, InMemory Qdrant, Test-User/Kunden.

---

## Querschnitt → Tests

| Querschnitt | Relevante Tests |
|---|---|
| Session/Auth | `test_auth.py` |
| Tenant | `test_tenant_isolation.py`, `test_global_customer.py` |
| Chat | `test_chats.py`, `test_agent.py` |
| Ingestion/Upload | `test_ingestion.py`, `test_upload_api.py`, `test_documents_api.py` |
| Admin Kunden | `test_admin_customers.py`, `test_customers.py` |
| Admin User | `test_admin_users.py` |
| Health | `test_health.py` |

Strategie: [`docs/10_testing_strategy.md`](../10_testing_strategy.md)

---

## Ausführung

```bash
cd backend && PYTHONPATH=. pytest -q
PYTHONPATH=. pytest app/tests/test_tenant_isolation.py -q  # Gate
```

Spiegel: `docs/docs/backend/app/tests/*.md`, `conftest.md`

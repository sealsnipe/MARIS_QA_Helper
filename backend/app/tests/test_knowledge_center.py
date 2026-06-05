from __future__ import annotations

from app.knowledge_center import create_knowledge_source, ingest_knowledge_contents
from app.models import KnowledgeContent
from app.tests.conftest import create_customer, create_user, login

INTEGRATION_TOKEN = "test-integration-token-secret"
INTEGRATION_USER_EMAIL = "integration@internal"


def _enable_integration(monkeypatch) -> None:
    monkeypatch.setenv("INTEGRATION_API_TOKEN", INTEGRATION_TOKEN)
    monkeypatch.setenv("INTEGRATION_USER_EMAIL", INTEGRATION_USER_EMAIL)
    from app import config

    config.get_settings.cache_clear()


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {INTEGRATION_TOKEN}"}


def _sample_item(**overrides) -> dict:
    base = {
        "title": "VPN Troubleshooting Guide",
        "summary": "Kurze Anleitung für VPN-Probleme.",
        "content": "Dies ist ein ausreichend langer Inhalt für die KB-Aufnahme.",
        "keywords": ["vpn", "netzwerk"],
        "external_id": "vpn-guide-1",
        "customer_id": "bg-frankfurt",
    }
    base.update(overrides)
    return base


def _seed(db_session) -> tuple:
    create_customer(db_session, "bg-frankfurt", "BG Frankfurt")
    create_customer(db_session, "kkrr", "KKRR")
    create_user(db_session, INTEGRATION_USER_EMAIL, "ignored", ("bg-frankfurt",))
    admin = create_user(db_session, "admin@example.com", "secret123", tuple(), is_admin=True)
    user = create_user(db_session, "user@example.com", "secret123", ("bg-frankfurt",))
    source = create_knowledge_source(db_session, "Test Agent", "agent-alpha")
    return admin, user, source


def test_sources_crud_admin_only(client, db_session):
    admin, user, _source = _seed(db_session)
    login(client, "admin@example.com", "secret123")

    response = client.get("/api/admin/knowledge-sources")
    assert response.status_code == 200
    assert len(response.json()["sources"]) == 1

    create_resp = client.post(
        "/api/admin/knowledge-sources",
        json={"name": "Jira Sync", "host_code": "jira-sync"},
    )
    assert create_resp.status_code == 200
    assert create_resp.json()["source"]["host_code"] == "jira-sync"

    login(client, "user@example.com", "secret123")
    denied = client.get("/api/admin/knowledge-sources")
    assert denied.status_code == 403


def test_ingest_unknown_host_code_rejected(client, db_session, monkeypatch):
    _enable_integration(monkeypatch)
    _seed(db_session)

    response = client.post(
        "/api/v1/knowledge-content",
        headers=_auth_headers(),
        json={"host_code": "missing", "items": [_sample_item()]},
    )
    assert response.status_code == 400
    assert response.json()["error"] == "unknown_source"


def test_ingest_creates_and_dedups_pending(client, db_session, monkeypatch):
    _enable_integration(monkeypatch)
    _seed(db_session)

    payload = {"host_code": "agent-alpha", "items": [_sample_item()]}
    first = client.post("/api/v1/knowledge-content", headers=_auth_headers(), json=payload)
    assert first.status_code == 200
    assert first.json()["created"] == 1

    updated_item = _sample_item(title="VPN Guide Updated")
    second = client.post(
        "/api/v1/knowledge-content",
        headers=_auth_headers(),
        json={"host_code": "agent-alpha", "items": [updated_item]},
    )
    assert second.status_code == 200
    assert second.json()["updated"] == 1

    rows = db_session.query(KnowledgeContent).all()
    assert len(rows) == 1
    assert rows[0].title == "VPN Guide Updated"


def test_ingest_partial_batch_invalid_customer(client, db_session, monkeypatch):
    _enable_integration(monkeypatch)
    _seed(db_session)

    response = client.post(
        "/api/v1/knowledge-content",
        headers=_auth_headers(),
        json={
            "host_code": "agent-alpha",
            "items": [
                _sample_item(external_id="ok-1"),
                _sample_item(external_id="bad-1", customer_id="unknown-slug"),
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["created"] == 1
    assert len(body["errors"]) == 1


def test_content_list_visibility_and_adopt(client, db_session, monkeypatch):
    _enable_integration(monkeypatch)
    _seed(db_session)
    ingest_knowledge_contents(db_session, "agent-alpha", [_sample_item()])

    login(client, "user@example.com", "secret123")
    listing = client.get("/api/tools/knowledge-center/contents")
    assert listing.status_code == 200
    contents = listing.json()["contents"]
    assert len(contents) == 1
    content_id = contents[0]["id"]

    adopt = client.post(
        f"/api/tools/knowledge-center/contents/{content_id}/adopt",
        json={"customer_id": "bg-frankfurt"},
    )
    assert adopt.status_code == 200
    assert adopt.json()["document_id"]
    assert adopt.json()["customer_id"] == "bg-frankfurt"

    row = db_session.get(KnowledgeContent, content_id)
    assert row is not None
    assert row.status == "adopted"
    assert row.adopted_document_id is not None


def test_adopt_requires_customer_access(client, db_session, monkeypatch):
    _enable_integration(monkeypatch)
    _seed(db_session)
    ingest_knowledge_contents(
        db_session,
        "agent-alpha",
        [_sample_item(customer_id="bg-frankfurt", external_id="frankfurt-only")],
    )

    login(client, "user@example.com", "secret123")
    content_id = client.get("/api/tools/knowledge-center/contents").json()["contents"][0]["id"]

    forbidden = client.post(
        f"/api/tools/knowledge-center/contents/{content_id}/adopt",
        json={"customer_id": "kkrr"},
    )
    assert forbidden.status_code == 403


def test_reject_and_double_adopt_conflict(client, db_session, monkeypatch):
    _enable_integration(monkeypatch)
    _seed(db_session)
    ingest_knowledge_contents(db_session, "agent-alpha", [_sample_item(external_id="reject-me")])

    login(client, "user@example.com", "secret123")
    content_id = client.get("/api/tools/knowledge-center/contents").json()["contents"][0]["id"]

    reject = client.post(f"/api/tools/knowledge-center/contents/{content_id}/reject")
    assert reject.status_code == 200

    conflict = client.post(
        f"/api/tools/knowledge-center/contents/{content_id}/adopt",
        json={"customer_id": "bg-frankfurt"},
    )
    assert conflict.status_code == 409


def test_knowledge_center_pages(client, db_session):
    admin, user, _source = _seed(db_session)

    login(client, "user@example.com", "secret123")
    content_page = client.get("/tools/knowledge-center")
    assert content_page.status_code == 200
    assert "Content Dashboard" in content_page.text

    sources_denied = client.get("/tools/knowledge-center/sources", follow_redirects=False)
    assert sources_denied.status_code == 302

    login(client, "admin@example.com", "secret123")
    sources_page = client.get("/tools/knowledge-center/sources")
    assert sources_page.status_code == 200
    assert "Host-Code" in sources_page.text


def test_null_suggested_customer_visible_to_assigned_user(client, db_session, monkeypatch):
    _enable_integration(monkeypatch)
    _seed(db_session)
    ingest_knowledge_contents(
        db_session,
        "agent-alpha",
        [_sample_item(customer_id=None, external_id="pool-1")],
    )

    login(client, "user@example.com", "secret123")
    listing = client.get("/api/tools/knowledge-center/contents")
    assert listing.status_code == 200
    assert len(listing.json()["contents"]) == 1

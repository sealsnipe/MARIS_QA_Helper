from __future__ import annotations

from unittest.mock import patch

from app.content_refine import ContentRefineResult
from app.knowledge_center import (
    HOST_CODE_CHAT_REFINE,
    HOST_CODE_USER_SUBMIT,
    create_knowledge_source,
    ensure_builtin_knowledge_sources,
    ingest_knowledge_contents,
)
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
    ensure_builtin_knowledge_sources(db_session)
    return admin, user, source


def test_sources_crud_admin_only(client, db_session):
    _admin, _user, _source = _seed(db_session)
    login(client, "admin@example.com", "secret123")

    response = client.get("/api/admin/knowledge-sources")
    assert response.status_code == 200
    assert any(row["host_code"] == HOST_CODE_USER_SUBMIT for row in response.json()["sources"])

    create_resp = client.post(
        "/api/admin/knowledge-sources",
        json={"name": "Jira Sync", "host_code": "jira-sync"},
    )
    assert create_resp.status_code == 200

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


def test_admin_dashboard_requires_admin(client, db_session):
    _seed(db_session)
    login(client, "user@example.com", "secret123")
    denied = client.get("/api/tools/knowledge-center/contents")
    assert denied.status_code == 403


def test_submit_without_ai(client, db_session):
    _seed(db_session)
    login(client, "user@example.com", "secret123")

    response = client.post(
        "/api/tools/knowledge-center/submit",
        json={
            "customer_id": "bg-frankfurt",
            "raw_text": "Dies ist ein Rohtext mit genügend Länge für die Einreichung.",
            "title": "Mein Vorschlag",
            "use_ai": False,
        },
    )
    assert response.status_code == 200
    body = response.json()["content"]
    assert body["host_code"] == HOST_CODE_USER_SUBMIT
    assert body["submitted_by_email"] == "user@example.com"
    assert body["original_content"] == body["content"]


@patch("app.knowledge_center.refine_content_with_llm")
def test_submit_with_ai(mock_refine, client, db_session):
    _seed(db_session)
    login(client, "user@example.com", "secret123")

    mock_refine.return_value = ContentRefineResult(
        title="VPN Guide",
        summary="Kurzfassung",
        keywords=["vpn"],
        content="Dies ist der überarbeitete Text mit genügend Länge.",
        revision={
            "version": 1,
            "changes": [
                {
                    "id": "c1",
                    "kind": "replace",
                    "sources": ["Rohtext"],
                    "target": "überarbeitete",
                    "anchor": "überarbeitete",
                }
            ],
            "stats": {"change_ratio": 0.2, "change_count": 1},
        },
    )

    response = client.post(
        "/api/tools/knowledge-center/submit",
        json={
            "customer_id": "bg-frankfurt",
            "raw_text": "Dies ist ein Rohtext mit genügend Länge für die Einreichung.",
            "use_ai": True,
            "preset": "clarify",
        },
    )
    assert response.status_code == 200
    body = response.json()["content"]
    assert body["host_code"] == HOST_CODE_CHAT_REFINE
    assert body["revision"] is not None
    assert body["has_revision"] is True


def test_adopt_requires_admin(client, db_session, monkeypatch):
    _enable_integration(monkeypatch)
    _seed(db_session)
    ingest_knowledge_contents(db_session, "agent-alpha", [_sample_item()])

    login(client, "admin@example.com", "secret123")
    content_id = client.get("/api/tools/knowledge-center/contents").json()["contents"][0]["id"]

    login(client, "user@example.com", "secret123")
    forbidden = client.post(
        f"/api/tools/knowledge-center/contents/{content_id}/adopt",
        json={"customer_id": "bg-frankfurt"},
    )
    assert forbidden.status_code == 403

    login(client, "admin@example.com", "secret123")
    adopt = client.post(
        f"/api/tools/knowledge-center/contents/{content_id}/adopt",
        json={"customer_id": "bg-frankfurt"},
    )
    assert adopt.status_code == 200


def test_my_contents_only_own(client, db_session):
    _seed(db_session)
    login(client, "user@example.com", "secret123")
    client.post(
        "/api/tools/knowledge-center/submit",
        json={
            "customer_id": "bg-frankfurt",
            "raw_text": "Mein eigener Vorschlag mit ausreichend Zeichen.",
            "use_ai": False,
        },
    )

    mine = client.get("/api/tools/knowledge-center/my-contents")
    assert mine.status_code == 200
    assert len(mine.json()["contents"]) == 1

    login(client, "admin@example.com", "secret123")
    admin_mine = client.get("/api/tools/knowledge-center/my-contents")
    assert admin_mine.status_code == 200
    assert len(admin_mine.json()["contents"]) == 0


def test_knowledge_center_pages(client, db_session):
    _seed(db_session)

    login(client, "user@example.com", "secret123")
    submit_page = client.get("/tools/knowledge-center/submit")
    assert submit_page.status_code == 200
    assert "Content vorschlagen" in submit_page.text

    dashboard_redirect = client.get("/tools/knowledge-center", follow_redirects=False)
    assert dashboard_redirect.status_code == 302
    assert dashboard_redirect.headers["location"] == "/tools/knowledge-center/submit"

    sources_denied = client.get("/tools/knowledge-center/sources", follow_redirects=False)
    assert sources_denied.status_code == 302

    login(client, "admin@example.com", "secret123")
    dashboard = client.get("/tools/knowledge-center")
    assert dashboard.status_code == 200
    sources_page = client.get("/tools/knowledge-center/sources")
    assert sources_page.status_code == 200

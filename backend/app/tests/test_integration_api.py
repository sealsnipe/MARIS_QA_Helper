from __future__ import annotations

from app.agent import ChatResult
from app.chats import list_messages
from app.tests.conftest import create_customer, create_user

INTEGRATION_TOKEN = "test-integration-token-secret"
INTEGRATION_USER_EMAIL = "integration@internal"


def _enable_integration(monkeypatch) -> None:
    monkeypatch.setenv("INTEGRATION_API_TOKEN", INTEGRATION_TOKEN)
    monkeypatch.setenv("INTEGRATION_USER_EMAIL", INTEGRATION_USER_EMAIL)
    from app import config

    config.get_settings.cache_clear()


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {INTEGRATION_TOKEN}"}


def _seed_integration_user(db_session) -> None:
    create_customer(db_session, "bg-frankfurt", "BG Frankfurt")
    create_user(db_session, INTEGRATION_USER_EMAIL, "ignored", ("bg-frankfurt",))


def test_ask_without_token_returns_401(client, db_session, monkeypatch):
    _enable_integration(monkeypatch)
    _seed_integration_user(db_session)

    response = client.post(
        "/api/v1/ask",
        json={"question": "Was ist VPN?", "customer_id": "bg-frankfurt"},
    )
    assert response.status_code == 401
    assert response.json() == {"error": "invalid_token"}


def test_ask_with_wrong_token_returns_401(client, db_session, monkeypatch):
    _enable_integration(monkeypatch)
    _seed_integration_user(db_session)

    response = client.post(
        "/api/v1/ask",
        headers={"Authorization": "Bearer wrong-token"},
        json={"question": "Was ist VPN?", "customer_id": "bg-frankfurt"},
    )
    assert response.status_code == 401
    assert response.json() == {"error": "invalid_token"}


def test_integration_disabled_returns_503(client, db_session, monkeypatch):
    monkeypatch.setenv("INTEGRATION_API_TOKEN", "")
    from app import config

    config.get_settings.cache_clear()
    _seed_integration_user(db_session)

    response = client.post(
        "/api/v1/ask",
        headers=_auth_headers(),
        json={"question": "Was ist VPN?", "customer_id": "bg-frankfurt"},
    )
    assert response.status_code == 503
    assert response.json() == {"error": "integration_disabled"}


def test_integration_user_missing_returns_503(client, db_session, monkeypatch):
    _enable_integration(monkeypatch)
    create_customer(db_session, "bg-frankfurt", "BG Frankfurt")

    response = client.post(
        "/api/v1/ask",
        headers=_auth_headers(),
        json={"question": "Was ist VPN?", "customer_id": "bg-frankfurt"},
    )
    assert response.status_code == 503
    assert response.json() == {"error": "integration_user_missing"}


def test_ask_success(client, db_session, monkeypatch):
    _enable_integration(monkeypatch)
    _seed_integration_user(db_session)
    monkeypatch.setattr(
        "app.integration_routes.run_agent",
        lambda *args, **kwargs: ChatResult(
            "Antwort [1]",
            [{"n": 1, "document_id": "d1", "title": "Doc", "chunk_index": 0, "score": 0.9}],
            False,
        ),
    )

    response = client.post(
        "/api/v1/ask",
        headers=_auth_headers(),
        json={"question": "Was ist VPN?", "customer_id": "bg-frankfurt"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "Antwort [1]"
    assert payload["no_context"] is False
    assert len(payload["sources"]) == 1
    assert payload["customer_id"] == "bg-frankfurt"
    assert payload["chat_id"]


def test_ask_persists_follow_up(client, db_session, monkeypatch):
    _enable_integration(monkeypatch)
    _seed_integration_user(db_session)
    monkeypatch.setattr(
        "app.integration_routes.run_agent",
        lambda *args, **kwargs: ChatResult("Erste Antwort", [], True),
    )

    first = client.post(
        "/api/v1/ask",
        headers=_auth_headers(),
        json={"question": "Frage eins", "customer_id": "bg-frankfurt"},
    )
    assert first.status_code == 200
    chat_id = first.json()["chat_id"]

    monkeypatch.setattr(
        "app.integration_routes.run_agent",
        lambda *args, **kwargs: ChatResult("Zweite Antwort", [], True),
    )
    second = client.post(
        "/api/v1/ask",
        headers=_auth_headers(),
        json={"question": "Frage zwei", "customer_id": "bg-frankfurt", "chat_id": chat_id},
    )
    assert second.status_code == 200
    assert second.json()["chat_id"] == chat_id

    messages = list_messages(db_session, chat_id)
    assert len(messages) == 4
    assert messages[0]["content"] == "Frage eins"
    assert messages[1]["content"] == "Erste Antwort"
    assert messages[2]["content"] == "Frage zwei"
    assert messages[3]["content"] == "Zweite Antwort"


def test_ask_forbidden_customer(client, db_session, monkeypatch):
    _enable_integration(monkeypatch)
    _seed_integration_user(db_session)

    response = client.post(
        "/api/v1/ask",
        headers=_auth_headers(),
        json={"question": "Hallo", "customer_id": "unknown-customer"},
    )
    assert response.status_code == 403
    assert response.json() == {"error": "forbidden_customer"}


def test_ask_empty_question(client, db_session, monkeypatch):
    _enable_integration(monkeypatch)
    _seed_integration_user(db_session)

    response = client.post(
        "/api/v1/ask",
        headers=_auth_headers(),
        json={"question": "   ", "customer_id": "bg-frankfurt"},
    )
    assert response.status_code == 400
    assert response.json() == {"error": "empty_question"}


def test_ask_unknown_chat_id(client, db_session, monkeypatch):
    _enable_integration(monkeypatch)
    _seed_integration_user(db_session)

    response = client.post(
        "/api/v1/ask",
        headers=_auth_headers(),
        json={
            "question": "Follow-up",
            "customer_id": "bg-frankfurt",
            "chat_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert response.status_code == 404
    assert response.json() == {"error": "not_found"}


def test_ask_scopes_run_agent_to_requested_customer(client, db_session, monkeypatch):
    _enable_integration(monkeypatch)
    _seed_integration_user(db_session)
    captured: dict = {}

    def fake_run(customer_id, message, top_k=None, **kwargs):
        captured["customer_id"] = customer_id
        captured["scope_customer_ids"] = kwargs.get("scope_customer_ids")
        return ChatResult("OK", [], True)

    monkeypatch.setattr("app.integration_routes.run_agent", fake_run)

    response = client.post(
        "/api/v1/ask",
        headers=_auth_headers(),
        json={"question": "Test", "customer_id": "bg-frankfurt", "top_k": 6},
    )
    assert response.status_code == 200
    assert captured["customer_id"] == "bg-frankfurt"
    assert captured["scope_customer_ids"] == ["bg-frankfurt"]

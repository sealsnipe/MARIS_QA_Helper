from app.agent import ChatResult
from app.tests.conftest import create_customer, create_user, login


def test_create_and_list_chats(client, db_session):
    create_customer(db_session, "acme", "Acme GmbH")
    create_user(db_session, "sven@example.com", "secret123", ("acme",))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "acme"})

    create = client.post("/api/chats")
    assert create.status_code == 200
    chat_id = create.json()["chat"]["id"]

    listed = client.get("/api/chats")
    assert listed.status_code == 200
    assert any(item["id"] == chat_id for item in listed.json()["chats"])


def test_chat_persists_messages(client, db_session, monkeypatch):
    monkeypatch.setattr(
        "app.routes.run_agent",
        lambda *args, **kwargs: ChatResult("Antworttext", [{"n": 1, "document_id": "d1", "title": "Doc", "chunk_index": 0, "score": 0.9}], False),
    )

    create_customer(db_session, "acme", "Acme GmbH")
    create_user(db_session, "sven@example.com", "secret123", ("acme",))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "acme"})

    response = client.post("/api/chat", json={"message": "Was ist VPN?"})
    assert response.status_code == 200
    chat_id = response.json()["chat_id"]

    detail = client.get(f"/api/chats/{chat_id}")
    assert detail.status_code == 200
    messages = detail.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["content"] == "Was ist VPN?"
    assert messages[1]["content"] == "Antworttext"


def test_chat_history_isolated_by_customer(client, db_session):
    create_customer(db_session, "acme", "Acme GmbH")
    create_customer(db_session, "globex", "Globex AG")
    create_user(db_session, "sven@example.com", "secret123", ("acme", "globex"))
    login(client, "sven@example.com", "secret123")

    client.post("/api/session/customer", json={"customer_id": "acme"})
    acme_chat_id = client.post("/api/chats").json()["chat"]["id"]

    client.post("/api/session/customer", json={"customer_id": "globex"})
    globex_chat_id = client.post("/api/chats").json()["chat"]["id"]

    globex_list = client.get("/api/chats")
    assert globex_list.status_code == 200
    globex_ids = {item["id"] for item in globex_list.json()["chats"]}
    assert globex_chat_id in globex_ids
    assert acme_chat_id not in globex_ids

    forbidden = client.get(f"/api/chats/{acme_chat_id}")
    assert forbidden.status_code == 403

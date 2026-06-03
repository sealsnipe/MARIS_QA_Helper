from app.customers import GLOBAL_CUSTOMER_ID
from app.tests.conftest import create_customer, create_user, login


def test_global_customer_in_nav_list(client, db_session):
    create_customer(db_session, GLOBAL_CUSTOMER_ID, "Global")
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")

    response = client.get("/api/customers")
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["customers"]]
    assert ids[0] == GLOBAL_CUSTOMER_ID
    assert "bg-ludwigshafen" in ids


def test_global_customer_switch(client, db_session):
    create_customer(db_session, GLOBAL_CUSTOMER_ID, "Global")
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")

    response = client.post("/api/session/customer", json={"customer_id": GLOBAL_CUSTOMER_ID})
    assert response.status_code == 200
    assert response.json()["active"] == GLOBAL_CUSTOMER_ID


def test_global_kb_is_read_only(client, db_session):
    create_customer(db_session, GLOBAL_CUSTOMER_ID, "Global")
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": GLOBAL_CUSTOMER_ID})

    listing = client.get("/api/documents")
    assert listing.status_code == 200
    body = listing.json()
    assert body["read_only"] is True
    assert body["customer_id"] == GLOBAL_CUSTOMER_ID

    blocked = client.post(
        "/api/documents/text",
        json={"title": "Test", "text": "Dieser Text ist lang genug für die Indexierung."},
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"] == "read_only_scope"

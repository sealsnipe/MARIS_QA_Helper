from app.tests.conftest import create_customer, create_user, login


def test_documents_text_endpoint_scoped_to_active_customer(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_customer(db_session, "kkrr", "Katholische Kliniken Rhein Ruhr")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen", "kkrr"))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "bg-ludwigshafen"})

    response = client.post(
        "/api/documents/text",
        json={
            "title": "VPN Runbook",
            "text": "BG Ludwigshafen VPN Eskalation: FortiGate prüfen, danach Netzwerkteam informieren.",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["document"]["customer_id"] == "bg-ludwigshafen"
    assert body["document"]["chunk_count"] >= 1

    listing = client.get("/api/documents")
    assert listing.status_code == 200
    assert len(listing.json()["documents"]) == 1

    client.post("/api/session/customer", json={"customer_id": "kkrr"})
    assert client.get("/api/documents").json()["documents"] == []


def test_production_customers_visible_for_admin(client, db_session):
    create_customer(db_session, "global", "Global")
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_customer(db_session, "bg-frankfurt", "BG Frankfurt")
    create_customer(db_session, "detmold-lippe", "Detmold Lippe")
    create_customer(db_session, "kkrr", "Katholische Kliniken Rhein Ruhr")
    create_user(
        db_session,
        "admin@example.com",
        "secret123",
        ("bg-ludwigshafen", "bg-frankfurt", "detmold-lippe", "kkrr"),
    )
    login(client, "admin@example.com", "secret123")

    response = client.get("/api/customers")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["customers"]}
    assert ids == {"global", "bg-ludwigshafen", "bg-frankfurt", "detmold-lippe", "kkrr"}

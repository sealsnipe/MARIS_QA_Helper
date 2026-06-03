from app.tests.conftest import create_customer, create_user, login


def test_admin_api_requires_admin(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")

    response = client.get("/api/admin/system-prompt")
    assert response.status_code == 403


def test_admin_can_read_and_write_prompt(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "admin@example.com", "secret123", ("bg-ludwigshafen",), is_admin=True)
    login(client, "admin@example.com", "secret123")

    get_response = client.get("/api/admin/system-prompt")
    assert get_response.status_code == 200

    put_response = client.put(
        "/api/admin/system-prompt",
        json={"customer_id": None, "content": "Du bist der Maris Support-Assistent."},
    )
    assert put_response.status_code == 200
    assert "Maris" in put_response.json()["content"]


def test_admin_page_redirects_for_non_admin(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")

    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/chat"

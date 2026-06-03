from app.tests.conftest import create_customer, create_user, login


def test_admin_customers_api_requires_admin(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")

    response = client.get("/api/admin/customers")
    assert response.status_code == 403


def test_admin_customers_crud(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "admin@example.com", "secret123", ("bg-ludwigshafen",), is_admin=True)
    login(client, "admin@example.com", "secret123")

    create_response = client.post(
        "/api/admin/customers",
        json={"customer_id": "kkrr", "name": "Katholische Kliniken Rhein Ruhr"},
    )
    assert create_response.status_code == 200
    assert create_response.json()["customer"]["id"] == "kkrr"

    list_response = client.get("/api/admin/customers")
    assert list_response.status_code == 200
    ids = {item["id"] for item in list_response.json()["customers"]}
    assert "kkrr" in ids

    me_response = client.get("/api/customers")
    assert "kkrr" in {item["id"] for item in me_response.json()["customers"]}

    update_response = client.patch(
        "/api/admin/customers/kkrr",
        json={"name": "KKRR"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["customer"]["name"] == "KKRR"

    delete_response = client.delete("/api/admin/customers/kkrr")
    assert delete_response.status_code == 200

    after_delete = client.get("/api/admin/customers")
    ids_after = {item["id"] for item in after_delete.json()["customers"]}
    assert "kkrr" not in ids_after


def test_admin_cannot_delete_global_customer(client, db_session):
    create_user(db_session, "admin@example.com", "secret123", (), is_admin=True)
    login(client, "admin@example.com", "secret123")

    response = client.delete("/api/admin/customers/global")
    assert response.status_code == 403


def test_admin_customers_page_redirects_for_non_admin(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")

    response = client.get("/admin/customers", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/chat"

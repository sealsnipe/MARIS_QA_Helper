from app.tests.conftest import create_customer, create_user, login


def test_admin_users_api_requires_admin(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")

    response = client.get("/api/admin/users")
    assert response.status_code == 403


def test_admin_users_crud(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_customer(db_session, "kkrr", "KKRR")
    admin = create_user(db_session, "admin@example.com", "secret123", ("bg-ludwigshafen",), is_admin=True)
    login(client, "admin@example.com", "secret123")

    create_response = client.post(
        "/api/admin/users",
        json={
            "email": "anna@example.com",
            "password": "secret123",
            "customer_ids": ["kkrr"],
            "is_admin": False,
        },
    )
    assert create_response.status_code == 200
    user_id = create_response.json()["user"]["id"]

    list_response = client.get("/api/admin/users")
    emails = {item["email"] for item in list_response.json()["users"]}
    assert "anna@example.com" in emails

    update_response = client.patch(
        f"/api/admin/users/{user_id}",
        json={
            "email": "anna@example.com",
            "customer_ids": ["bg-ludwigshafen", "kkrr"],
            "is_admin": False,
            "is_active": True,
        },
    )
    assert update_response.status_code == 200
    assert set(update_response.json()["user"]["customer_ids"]) == {"bg-ludwigshafen", "kkrr"}

    delete_response = client.delete(f"/api/admin/users/{user_id}")
    assert delete_response.status_code == 200

    after = client.get("/api/admin/users")
    anna = next(item for item in after.json()["users"] if item["email"] == "anna@example.com")
    assert anna["is_active"] is False

    self_delete = client.delete(f"/api/admin/users/{admin.id}")
    assert self_delete.status_code == 403


def test_admin_roles_page_redirects_for_non_admin(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")

    response = client.get("/admin/roles", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/chat"


def test_admin_kb_redirects_for_admin(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "admin@example.com", "secret123", ("bg-ludwigshafen",), is_admin=True)
    login(client, "admin@example.com", "secret123")

    response = client.get("/kb", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/admin/knowledge"

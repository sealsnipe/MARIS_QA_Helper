from sqlalchemy import select

from app.models import UserCustomer
from app.roles_admin import create_admin_role
from app.tests.conftest import create_customer, create_user, login


def test_admin_roles_api_requires_admin(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")

    response = client.get("/api/admin/roles")
    assert response.status_code == 403


def test_admin_roles_crud(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_customer(db_session, "kkrr", "KKRR")
    create_user(db_session, "admin@example.com", "secret123", ("bg-ludwigshafen",), is_admin=True)
    login(client, "admin@example.com", "secret123")

    create_response = client.post(
        "/api/admin/roles",
        json={
            "name": "Support Frankfurt",
            "customer_ids": ["kkrr"],
            "is_admin": False,
            "auto_add_new_customers": True,
        },
    )
    assert create_response.status_code == 200
    role_id = create_response.json()["role"]["id"]
    assert create_response.json()["role"]["auto_add_new_customers"] is True

    list_response = client.get("/api/admin/roles")
    names = {item["name"] for item in list_response.json()["roles"]}
    assert "Support Frankfurt" in names

    update_response = client.patch(
        f"/api/admin/roles/{role_id}",
        json={
            "name": "Support Rhein-Ruhr",
            "customer_ids": ["bg-ludwigshafen", "kkrr"],
            "is_admin": True,
            "auto_add_new_customers": True,
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()["role"]
    assert updated["name"] == "Support Rhein-Ruhr"
    assert updated["is_admin"] is True
    assert set(updated["customer_ids"]) == {"bg-ludwigshafen", "kkrr"}

    delete_response = client.delete(f"/api/admin/roles/{role_id}")
    assert delete_response.status_code == 200


def test_user_role_preset_applies_admin_and_customers(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_customer(db_session, "kkrr", "KKRR")
    create_user(db_session, "admin@example.com", "secret123", ("bg-ludwigshafen",), is_admin=True)
    login(client, "admin@example.com", "secret123")

    role = create_admin_role(
        db_session,
        "Preset Admin",
        ["kkrr"],
        is_admin=True,
        auto_add_new_customers=False,
    )

    create_response = client.post(
        "/api/admin/users",
        json={
            "email": "preset@example.com",
            "password": "secret123",
            "customer_ids": [],
            "role_ids": [role.id],
            "is_admin": False,
        },
    )
    assert create_response.status_code == 200
    payload = create_response.json()["user"]
    assert payload["is_admin"] is True
    assert payload["customer_ids"] == ["kkrr"]
    assert payload["role_ids"] == [role.id]


def test_auto_add_new_customer_for_role_users(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    admin = create_user(db_session, "admin@example.com", "secret123", ("bg-ludwigshafen",), is_admin=True)
    login(client, "admin@example.com", "secret123")

    role = create_admin_role(
        db_session,
        "Auto Support",
        ["bg-ludwigshafen"],
        is_admin=False,
        auto_add_new_customers=True,
    )

    create_user_response = client.post(
        "/api/admin/users",
        json={
            "email": "auto@example.com",
            "password": "secret123",
            "customer_ids": [],
            "role_ids": [role.id],
            "is_admin": False,
        },
    )
    assert create_user_response.status_code == 200
    user_id = create_user_response.json()["user"]["id"]

    create_customer_response = client.post(
        "/api/admin/customers",
        json={"customer_id": "kkrr", "name": "Katholische Kliniken Rhein Ruhr"},
    )
    assert create_customer_response.status_code == 200

    users_response = client.get("/api/admin/users")
    auto_user = next(item for item in users_response.json()["users"] if item["id"] == user_id)
    assert set(auto_user["customer_ids"]) == {"bg-ludwigshafen", "kkrr"}

    roles_response = client.get("/api/admin/roles")
    auto_role = next(item for item in roles_response.json()["roles"] if item["id"] == role.id)
    assert "kkrr" in auto_role["customer_ids"]

    admin_after = next(item for item in users_response.json()["users"] if item["id"] == admin.id)
    assert "kkrr" in admin_after["customer_ids"]

    memberships = db_session.scalars(
        select(UserCustomer.customer_id).where(UserCustomer.user_id == user_id)
    ).all()
    assert set(memberships) == {"bg-ludwigshafen", "kkrr"}

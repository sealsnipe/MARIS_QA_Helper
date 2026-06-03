import asyncio
from unittest.mock import MagicMock

import pytest

from app.customers import collection_name, validate_customer_slug
from app.tenant import ForbiddenCustomerError, get_current_customer
from app.tests.conftest import create_customer, create_user, login


def test_validate_customer_slug_accepts_production_ids():
    assert validate_customer_slug("bg-ludwigshafen")
    assert validate_customer_slug("kkrr")
    assert validate_customer_slug("foo_bar-1")


@pytest.mark.parametrize(
    "invalid_slug",
    ["BG Ludwigshafen", "../bad-slug", "bad/b", "bad b", ""],
)
def test_validate_customer_slug_rejects_invalid(invalid_slug):
    assert not validate_customer_slug(invalid_slug)


def test_collection_name_builds_prefixed_slug():
    assert collection_name("bg-ludwigshafen", prefix="kb_") == "kb_bg-ludwigshafen"


def test_collection_name_rejects_invalid_slug():
    with pytest.raises(ValueError):
        collection_name("../bad-slug")


def test_list_customers_only_returns_assigned(client, db_session):
    create_customer(db_session, "global", "Global")
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_customer(db_session, "kkrr", "Katholische Kliniken Rhein Ruhr")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen", "kkrr"))
    login(client, "sven@example.com", "secret123")

    response = client.get("/api/customers")
    assert response.status_code == 200
    body = response.json()
    assert {item["id"] for item in body["customers"]} == {"global", "bg-ludwigshafen", "kkrr"}
    assert body["customers"][0]["id"] == "global"
    assert body["active"] is None


def test_single_customer_user_gets_auto_selected_on_login(client, db_session):
    create_customer(db_session, "kkrr", "Katholische Kliniken Rhein Ruhr")
    create_user(db_session, "anna@example.com", "secret123", ("kkrr",))
    login(client, "anna@example.com", "secret123")

    response = client.get("/api/customers")
    assert response.status_code == 200
    assert response.json()["active"] == "kkrr"


def test_customer_switch_sets_active_session(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_customer(db_session, "kkrr", "Katholische Kliniken Rhein Ruhr")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen", "kkrr"))
    login(client, "sven@example.com", "secret123")

    response = client.post("/api/session/customer", json={"customer_id": "kkrr"})
    assert response.status_code == 200
    assert response.json() == {"active": "kkrr"}
    assert client.get("/api/customers").json()["active"] == "kkrr"


def test_forbidden_customer_when_not_assigned(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_customer(db_session, "kkrr", "Katholische Kliniken Rhein Ruhr")
    create_user(db_session, "anna@example.com", "secret123", ("kkrr",))
    login(client, "anna@example.com", "secret123")

    response = client.post("/api/session/customer", json={"customer_id": "bg-ludwigshafen"})
    assert response.status_code == 403
    assert response.json() == {"error": "forbidden_customer"}


def test_unknown_customer_returns_404(client, db_session):
    create_customer(db_session, "kkrr", "Katholische Kliniken Rhein Ruhr")
    create_user(db_session, "anna@example.com", "secret123", ("kkrr",))
    login(client, "anna@example.com", "secret123")

    response = client.post("/api/session/customer", json={"customer_id": "missing"})
    assert response.status_code == 404
    assert response.json() == {"error": "not_found"}


def test_tenant_scoped_route_requires_active_customer(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_customer(db_session, "kkrr", "Katholische Kliniken Rhein Ruhr")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen", "kkrr"))
    login(client, "sven@example.com", "secret123")

    blocked = client.get("/api/tenant-check")
    assert blocked.status_code == 403
    assert blocked.json() == {"error": "forbidden_customer"}

    client.post("/api/session/customer", json={"customer_id": "bg-ludwigshafen"})
    allowed = client.get("/api/tenant-check")
    assert allowed.status_code == 200
    assert allowed.json()["customer_id"] == "bg-ludwigshafen"


def test_tenant_scoped_route_rejects_foreign_customer_in_session(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_customer(db_session, "kkrr", "Katholische Kliniken Rhein Ruhr")
    user = create_user(db_session, "anna@example.com", "secret123", ("kkrr",))

    request = MagicMock()
    request.session = {"customer_id": "bg-ludwigshafen"}

    with pytest.raises(ForbiddenCustomerError):
        asyncio.run(get_current_customer(request=request, user=user, db=db_session))

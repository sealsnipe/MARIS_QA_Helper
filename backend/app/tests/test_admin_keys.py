from app.customers import ensure_global_customer, list_customers_for_nav, GLOBAL_CUSTOMER_ID
from app.tests.conftest import create_customer, create_user, login


def test_admin_without_assignments_sees_all_tenants_in_nav(db_session):
    ensure_global_customer(db_session)
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_customer(db_session, "kkrr", "KKRR")
    admin = create_user(db_session, "lonely-admin@example.com", "secret123", tuple(), is_admin=True)
    nav = list_customers_for_nav(db_session, admin)
    ids = [c.id for c in nav]
    assert ids[0] == GLOBAL_CUSTOMER_ID
    assert "bg-ludwigshafen" in ids
    assert "kkrr" in ids


def test_admin_keys_page_shows_global_nav_not_unassigned(client, db_session):
    ensure_global_customer(db_session)
    create_user(db_session, "keys-admin@example.com", "secret123", tuple(), is_admin=True)
    login(client, "keys-admin@example.com", "secret123")

    resp = client.get("/admin/keys/assignments")
    assert resp.status_code == 200
    assert "Kein Kunde zugeordnet" not in resp.text
    assert 'data-nav-mode="global"' in resp.text


def test_admin_keys_redirect(client, db_session):
    create_user(db_session, "admin@example.com", "secret123", tuple(), is_admin=True)
    login(client, "admin@example.com", "secret123")
    resp = client.get("/admin/keys", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/admin/keys/assignments"


def test_admin_keys_requires_admin(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")

    resp = client.get("/api/admin/keys")
    assert resp.status_code == 403

    resp = client.get("/admin/keys", follow_redirects=False)
    assert resp.status_code in (302, 307)


def test_admin_keys_presets_page_renders(client, db_session):
    create_user(db_session, "admin2@example.com", "secret123", tuple(), is_admin=True)
    login(client, "admin2@example.com", "secret123")

    resp = client.get("/admin/keys/presets")
    assert resp.status_code == 200
    assert "Presets" in resp.text


def test_admin_keys_get_and_patch(client, db_session):
    create_user(db_session, "admin@example.com", "secret123", ("bg-ludwigshafen",), is_admin=True)
    login(client, "admin@example.com", "secret123")

    r = client.get("/api/admin/keys")
    assert r.status_code == 200
    data = r.json()
    assert "presets" in data and "bindings" in data and "embedding" in data
    assert "test-openai-key" not in str(data)

    r3 = client.patch("/api/admin/keys/embedding", json={"api_key": "sk-embed-1234567890"})
    assert r3.status_code == 200
    assert r3.json()["embedding"]["api_key_masked"].endswith("7890")

    r5 = client.patch("/api/admin/keys/integration", json={"api_key": ""})
    assert r5.status_code == 200
    assert r5.json()["integration"]["enabled"] is False


def test_admin_keys_assignments_page_renders(client, db_session):
    create_user(db_session, "admin2@example.com", "secret123", tuple(), is_admin=True)
    login(client, "admin2@example.com", "secret123")

    resp = client.get("/admin/keys/assignments")
    assert resp.status_code == 200
    assert "Zuordnung" in resp.text

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

    resp = client.get("/admin/keys")
    assert resp.status_code == 200
    assert "Kein Kunde zugeordnet" not in resp.text
    assert 'data-nav-mode="global"' in resp.text


def test_admin_keys_requires_admin(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")

    resp = client.get("/api/admin/keys")
    assert resp.status_code == 403

    resp = client.get("/admin/keys", follow_redirects=False)
    assert resp.status_code in (302, 307)


def test_admin_keys_get_and_patch(client, db_session):
    create_user(db_session, "admin@example.com", "secret123", ("bg-ludwigshafen",), is_admin=True)
    login(client, "admin@example.com", "secret123")

    # initial (from env placeholder in tests)
    r = client.get("/api/admin/keys")
    assert r.status_code == 200
    data = r.json()
    assert "chat" in data and "embedding" in data and "similarity" in data and "integration" in data
    # masked, never the real key
    assert "test-openai-key" not in str(data)

    # patch chat key (also force api_key mode so it appears in chat section)
    r2 = client.patch("/api/admin/keys/chat", json={"auth_mode": "api_key", "api_key": "sk-test-1234567890abcdef"})
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["chat"]["api_key_masked"].endswith("cdef")

    # patch embedding
    r3 = client.patch("/api/admin/keys/embedding", json={"api_key": "sk-embed-1234567890"})
    assert r3.status_code == 200

    # patch similarity to custom + key
    r4 = client.patch("/api/admin/keys/similarity", json={"mode": "custom", "api_key": "sk-sim-abcdef123456"})
    assert r4.status_code == 200
    d4 = r4.json()
    assert d4["similarity"]["mode"] == "custom"
    assert d4["similarity"]["api_key_masked"].endswith("3456")

    # integration empty disables
    r5 = client.patch("/api/admin/keys/integration", json={"api_key": ""})
    assert r5.status_code == 200
    assert r5.json()["integration"]["enabled"] is False

    # switch back
    r6 = client.patch("/api/admin/keys/similarity", json={"mode": "same_as_chat"})
    assert r6.status_code == 200
    assert r6.json()["similarity"]["mode"] == "same_as_chat"


def test_admin_keys_page_renders_for_admin(client, db_session):
    create_user(db_session, "admin2@example.com", "secret123", tuple(), is_admin=True)
    login(client, "admin2@example.com", "secret123")

    resp = client.get("/admin/keys", follow_redirects=False)
    assert resp.status_code == 200
    assert "Keys" in resp.text or "api/admin/keys" in resp.text

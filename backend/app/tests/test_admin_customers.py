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


def test_rename_tenant_customer_migrates_refs_and_qdrant(db_session, fake_vector_store):
    """Direct (no client): create tenant + data, rename, verify all wirings (sqlite refs, prompt scope, qdrant coll+payload, no old left)."""
    from app.customers import create_tenant_customer, rename_tenant_customer
    from app.models import Chunk, Customer, Document, SystemPrompt, UserCustomer
    from sqlalchemy import select
    from app.qdrant_store import get_vector_store

    # proper create (would link admins if present)
    c = create_tenant_customer(db_session, "oldk", "Old Kunde")
    assert c.id == "oldk"

    # KB data
    doc = Document(
        id="doc-rename-1",
        customer_id="oldk",
        title="Testdoc",
        source_type="manual",
        chunk_count=1,
        status="indexed",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    db_session.add(doc)
    ch = Chunk(
        id="chunk-1",
        document_id="doc-rename-1",
        customer_id="oldk",
        chunk_index=0,
        text="hello world",
        qdrant_point_id="chunk-1",
        created_at="2026-01-01T00:00:00Z",
    )
    db_session.add(ch)

    # membership (for completeness)
    if not db_session.scalar(select(UserCustomer).where(UserCustomer.customer_id == "oldk")):
        # no real user needed for rename test
        pass

    db_session.commit()

    # per-cust prompt
    p = SystemPrompt(scope="oldk", customer_id="oldk", content="prompt-old", updated_at="2026-01-01T00:00:00Z", updated_by="t")
    db_session.add(p)
    db_session.commit()

    # vector under old
    vs = get_vector_store()
    vs.upsert("oldk", [
        ("pt1", [0.1]*1536, {"customer_id": "oldk", "text": "hi", "document_id": "doc-rename-1"})
    ])

    # rename (this is what the admin PATCH calls)
    newc = rename_tenant_customer(db_session, "oldk", "newk")
    assert newc.id == "newk"
    assert newc.name == "Old Kunde"

    # sqlite moved
    assert db_session.get(Customer, "oldk") is None
    assert db_session.get(Customer, "newk") is not None
    assert db_session.get(Document, "doc-rename-1").customer_id == "newk"
    assert db_session.scalar(select(Chunk).where(Chunk.id == "chunk-1")).customer_id == "newk"

    # prompt scope moved
    assert db_session.get(SystemPrompt, "newk").content == "prompt-old"
    assert db_session.get(SystemPrompt, "oldk") is None

    # qdrant moved + payload refreshed
    assert "kb_newk" in vs.collections
    assert "kb_oldk" not in vs.collections or not vs.collections.get("kb_oldk")
    nb = vs.collections.get("kb_newk", {})
    assert any((pl or {}).get("customer_id") == "newk" for _pid, (_v, pl) in nb.items())

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


def test_admin_root_redirects_to_customers(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "admin@example.com", "secret123", ("bg-ludwigshafen",), is_admin=True)
    login(client, "admin@example.com", "secret123")

    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/admin/customers"


def test_admin_subpages_require_admin(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")

    for path in ("/admin/knowledge", "/admin/prompts", "/admin/users"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/chat"


def test_admin_can_get_and_update_document(client, db_session, fake_vector_store, fake_embeddings):
    from app.ingestion import ingest_text

    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "admin@example.com", "secret123", ("bg-ludwigshafen",), is_admin=True)
    login(client, "admin@example.com", "secret123")

    doc = ingest_text(
        db_session,
        customer_id="bg-ludwigshafen",
        title="Systemaufbau",
        text="Beschreibung des Kundensystems mit ausreichend Zeichen für die Admin-Bearbeitung.",
        embeddings=fake_embeddings,
        vector_store=fake_vector_store,
    ).document

    get_response = client.get(f"/api/admin/customers/bg-ludwigshafen/documents/{doc.id}")
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["document"]["title"] == "Systemaufbau"
    assert "Kundensystems" in body["text"]
    assert body["editable"] is True

    put_response = client.put(
        f"/api/admin/customers/bg-ludwigshafen/documents/{doc.id}",
        json={
            "title": "Systemaufbau v2",
            "text": "Aktualisierte Beschreibung des Kundensystems mit genügend Text für Re-Index.",
        },
    )
    assert put_response.status_code == 200
    assert put_response.json()["document"]["title"] == "Systemaufbau v2"

    wrong_customer = client.put(
        f"/api/admin/customers/kkrr/documents/{doc.id}",
        json={"title": "X", "text": "Falscher Mandant mit genügend Zeichen für den Testfall."},
    )
    assert wrong_customer.status_code == 404

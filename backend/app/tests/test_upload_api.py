from app.tests.conftest import create_customer, create_user, login


def test_upload_txt_only(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "bg-ludwigshafen"})

    content = b"Dies ist ein Testdokument mit genug Inhalt fuer die Indexierung."
    response = client.post(
        "/api/documents",
        files={"file": ("notes.txt", content, "text/plain")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["document"]["source_type"] == "txt"
    assert payload["document"]["status"] == "indexed"
    assert payload["document"]["title"] == "notes"
    assert payload["document"]["chunk_count"] >= 1


def test_upload_text_only(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "bg-ludwigshafen"})

    response = client.post(
        "/api/documents",
        data={"title": "Manueller Eintrag", "text": "Dies ist reiner Text mit ausreichend Laenge."},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["document"]["source_type"] == "manual"
    assert payload["document"]["title"] == "Manueller Eintrag"


def test_upload_combined_text_and_file(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "bg-ludwigshafen"})

    file_content = b"Dateiinhalt mit genuegend Zeichen fuer die Indexierung."
    response = client.post(
        "/api/documents",
        data={"title": "Kombi-Dokument", "text": "Einleitung aus dem Webformular."},
        files={"file": ("anhang.txt", file_content, "text/plain")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["document"]["title"] == "Kombi-Dokument"
    assert payload["document"]["source_type"] == "txt"


def test_upload_unsupported_type(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "bg-ludwigshafen"})

    response = client.post(
        "/api/documents",
        files={"file": ("bad.exe", b"data", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert response.json()["error"] == "unsupported_file_type"


def test_upload_requires_content(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "bg-ludwigshafen"})

    response = client.post("/api/documents", data={})
    assert response.status_code == 400
    assert response.json()["error"] == "empty_text"


def test_upload_extraction_failure_does_not_persist_document(client, db_session, monkeypatch):
    from app.ingestion import list_documents
    from app.loaders.errors import LoaderError

    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "bg-ludwigshafen"})

    def fail_load(*_args, **_kwargs):
        raise LoaderError("extraction_failed")

    monkeypatch.setattr("app.upload.load_document", fail_load)

    response = client.post(
        "/api/documents",
        files={"file": ("scan.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert response.status_code == 422
    assert response.json()["error"] == "extraction_failed"
    assert list_documents(db_session, "bg-ludwigshafen") == []

from __future__ import annotations

from app.content_hash import content_sha256_from_text
from app.duplicates import find_duplicate_document
from app.ingestion import ingest_text
from app.tests.conftest import create_customer, create_user, login


def test_content_sha256_ignores_short_text() -> None:
    assert content_sha256_from_text("zu kurz") is None


def test_content_sha256_is_stable_for_normalized_text() -> None:
    text = "Gleicher Inhalt mit genug Zeichen fuer den Hash."
    first = content_sha256_from_text(text)
    second = content_sha256_from_text("  Gleicher Inhalt mit genug Zeichen fuer den Hash.  ")
    assert first is not None
    assert first == second


def test_find_duplicate_document_scoped_to_customer(db_session, fake_vector_store, fake_embeddings) -> None:
    create_customer(db_session, "acme", "Acme")
    create_customer(db_session, "globex", "Globex")
    text = "Identischer Wissensinhalt mit ausreichend Laenge fuer Stufe eins."

    ingest_text(
        db_session,
        customer_id="acme",
        title="Acme Original",
        text=text,
        embeddings=fake_embeddings,
        vector_store=fake_vector_store,
    )

    assert find_duplicate_document(db_session, "acme", text) is not None
    assert find_duplicate_document(db_session, "globex", text) is None


def test_inspect_upload_reports_duplicate(db_session, fake_vector_store, fake_embeddings) -> None:
    from app.upload import inspect_upload

    create_customer(db_session, "acme", "Acme")
    text = b"Dies ist ein Testdokument mit genug Inhalt fuer die Duplikaterkennung."
    ingest_text(
        db_session,
        customer_id="acme",
        title="Bestehend",
        text=text.decode("utf-8"),
        embeddings=fake_embeddings,
        vector_store=fake_vector_store,
    )

    payload = inspect_upload(db_session, "acme", text, "notes.txt")
    assert payload["duplicate"] is not None
    assert payload["duplicate"]["title"] == "Bestehend"
    assert payload["content_sha256"] is not None


def test_upload_rejects_duplicate_without_allow_flag(client, db_session, fake_vector_store, fake_embeddings) -> None:
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "bg-ludwigshafen"})

    content = b"Dies ist ein Testdokument mit genug Inhalt fuer die Indexierung."
    first = client.post(
        "/api/documents",
        files={"file": ("notes.txt", content, "text/plain")},
    )
    assert first.status_code == 200

    second = client.post(
        "/api/documents",
        files={"file": ("copy.txt", content, "text/plain")},
    )
    assert second.status_code == 409
    assert second.json()["error"] == "duplicate_document"


def test_upload_allows_duplicate_with_allow_flag(client, db_session, fake_vector_store, fake_embeddings) -> None:
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "bg-ludwigshafen"})

    content = b"Dies ist ein Testdokument mit genug Inhalt fuer die Indexierung."
    assert client.post(
        "/api/documents",
        files={"file": ("notes.txt", content, "text/plain")},
    ).status_code == 200

    allowed = client.post(
        "/api/documents",
        data={"allow_duplicate": "true"},
        files={"file": ("copy.txt", content, "text/plain")},
    )
    assert allowed.status_code == 200
    assert allowed.json()["document"]["title"] == "copy"

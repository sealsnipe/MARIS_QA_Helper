import pytest

from app.customers import collection_name
from app.ingestion import (
    IngestionError,
    delete_document,
    get_document_text,
    ingest_text,
    list_documents,
    reindex_document,
    update_document_content,
)
from app.tests.conftest import create_customer


def test_ingest_success_writes_sqlite_and_qdrant(db_session, fake_vector_store, fake_embeddings):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    text = "Dies ist ein ausreichend langer Support-Text für die Indexierung im BG Ludwigshafen-Mandanten."

    result = ingest_text(
        db_session,
        customer_id="bg-ludwigshafen",
        title="BG Ludwigshafen FAQ",
        text=text,
        source_type="manual",
        embeddings=fake_embeddings,
        vector_store=fake_vector_store,
    )

    assert result.document.status == "indexed"
    assert result.document.chunk_count >= 1
    assert result.document.customer_id == "bg-ludwigshafen"

    docs = list_documents(db_session, "bg-ludwigshafen")
    assert len(docs) == 1
    assert docs[0]["title"] == "BG Ludwigshafen FAQ"

    bucket = fake_vector_store.collections[collection_name("bg-ludwigshafen")]
    chunk_points = [payload for _, payload in bucket.values() if payload.get("kind") != "document_fingerprint"]
    assert len(chunk_points) == result.document.chunk_count
    assert any(payload.get("kind") == "document_fingerprint" for _, payload in bucket.values())


def test_ingest_rejects_empty_text(db_session, fake_vector_store, fake_embeddings):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    with pytest.raises(IngestionError) as exc:
        ingest_text(
            db_session,
            customer_id="bg-ludwigshafen",
            title="Leer",
            text="kurz",
            embeddings=fake_embeddings,
            vector_store=fake_vector_store,
        )
    assert exc.value.code == "empty_text"
    assert list_documents(db_session, "bg-ludwigshafen") == []


def test_embedding_failure_does_not_create_indexed_document(db_session, fake_vector_store):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")

    class BrokenEmbeddings:
        def embed_documents(self, texts):
            raise RuntimeError("boom")

        def embed_query(self, text):
            raise RuntimeError("boom")

    with pytest.raises(IngestionError) as exc:
        ingest_text(
            db_session,
            customer_id="bg-ludwigshafen",
            title="Fail",
            text="Dies ist ein ausreichend langer Text für den Embedding-Fehlerfall im Test.",
            embeddings=BrokenEmbeddings(),
            vector_store=fake_vector_store,
        )
    assert exc.value.code == "embedding_failed"
    assert list_documents(db_session, "bg-ludwigshafen") == []


def test_delete_document_scoped_to_customer(db_session, fake_vector_store, fake_embeddings):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_customer(db_session, "kkrr", "Katholische Kliniken Rhein Ruhr")

    acme_doc = ingest_text(
        db_session,
        customer_id="bg-ludwigshafen",
        title="BG Ludwigshafen Only",
        text="Nur BG Ludwigshafen sichtbar — ausreichend langer Text für den Delete-Isolationstest.",
        embeddings=fake_embeddings,
        vector_store=fake_vector_store,
    ).document

    assert delete_document(db_session, "kkrr", acme_doc.id, vector_store=fake_vector_store) is False
    assert delete_document(db_session, "bg-ludwigshafen", acme_doc.id, vector_store=fake_vector_store) is True
    assert list_documents(db_session, "bg-ludwigshafen") == []


def test_get_document_text_uses_source_text(db_session, fake_vector_store, fake_embeddings):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    original = "Dies ist ein ausreichend langer Support-Text für source_text und Bearbeiten im Test."
    result = ingest_text(
        db_session,
        customer_id="bg-ludwigshafen",
        title="Quelle",
        text=original,
        embeddings=fake_embeddings,
        vector_store=fake_vector_store,
    )
    loaded = get_document_text(db_session, "bg-ludwigshafen", result.document.id)
    assert loaded is not None
    document, text = loaded
    assert document.source_text == original
    assert text == original


def test_update_document_content_reindexes(db_session, fake_vector_store, fake_embeddings):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    created = ingest_text(
        db_session,
        customer_id="bg-ludwigshafen",
        title="Alt",
        text="Alter Inhalt mit genügend Zeichen für die Wissensdatenbank und den Update-Test.",
        embeddings=fake_embeddings,
        vector_store=fake_vector_store,
    ).document
    doc_id = created.id
    created_at = created.created_at

    updated_text = "Neuer Mandanten-Überblick mit genügend Zeichen für die Re-Indexierung nach dem Speichern."
    result = update_document_content(
        db_session,
        "bg-ludwigshafen",
        doc_id,
        "Neu",
        updated_text,
        embeddings=fake_embeddings,
        vector_store=fake_vector_store,
    )

    assert result.document.id == doc_id
    assert result.document.created_at == created_at
    assert result.document.title == "Neu"
    assert result.document.source_text == updated_text
    assert result.document.status == "indexed"
    bucket = fake_vector_store.collections[collection_name("bg-ludwigshafen")]
    chunk_points = [payload for _, payload in bucket.values() if payload.get("kind") != "document_fingerprint"]
    assert len(chunk_points) == result.document.chunk_count
    assert any(payload.get("kind") == "document_fingerprint" for _, payload in bucket.values())


def test_reindex_document_restores_lost_vectors(db_session, fake_vector_store, fake_embeddings):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    created = ingest_text(
        db_session,
        customer_id="bg-ludwigshafen",
        title="Vergütung Rufbereitschaft",
        text="Vergütungstabelle für die 24/7-Rufbereitschaft mit genügend Zeichen für den Re-Index-Test.",
        embeddings=fake_embeddings,
        vector_store=fake_vector_store,
    ).document
    doc_id = created.id
    created_at = created.created_at
    source_type = created.source_type

    # Schadensfall: Qdrant-Punkte weg (z. B. Collection-Reset), SQLite intakt.
    bucket = fake_vector_store.collections[collection_name("bg-ludwigshafen")]
    bucket.clear()

    result = reindex_document(
        db_session,
        "bg-ludwigshafen",
        doc_id,
        embeddings=fake_embeddings,
        vector_store=fake_vector_store,
    )

    assert result.document.id == doc_id
    assert result.document.created_at == created_at
    assert result.document.title == "Vergütung Rufbereitschaft"
    assert result.document.source_type == source_type
    assert result.document.status == "indexed"
    chunk_points = [payload for _, payload in bucket.values() if payload.get("kind") != "document_fingerprint"]
    assert len(chunk_points) == result.document.chunk_count >= 1
    assert any(payload.get("kind") == "document_fingerprint" for _, payload in bucket.values())


def test_reindex_document_wrong_customer_raises_not_found(db_session, fake_vector_store, fake_embeddings):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_customer(db_session, "kkrr", "KKRR")
    doc = ingest_text(
        db_session,
        customer_id="bg-ludwigshafen",
        title="X",
        text="Isolationstest für Re-Index mit genügend Zeichen in diesem Dokument.",
        embeddings=fake_embeddings,
        vector_store=fake_vector_store,
    ).document

    with pytest.raises(IngestionError) as exc:
        reindex_document(db_session, "kkrr", doc.id, embeddings=fake_embeddings, vector_store=fake_vector_store)
    assert exc.value.code == "not_found"


def test_update_document_wrong_customer_raises_not_found(db_session, fake_vector_store, fake_embeddings):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_customer(db_session, "kkrr", "KKRR")
    doc = ingest_text(
        db_session,
        customer_id="bg-ludwigshafen",
        title="X",
        text="Isolationstest für Update mit genügend Zeichen in diesem Dokument.",
        embeddings=fake_embeddings,
        vector_store=fake_vector_store,
    ).document

    with pytest.raises(IngestionError) as exc:
        update_document_content(
            db_session,
            "kkrr",
            doc.id,
            "Y",
            "Falscher Mandant aber genügend Zeichen für Validierung im Test.",
            embeddings=fake_embeddings,
            vector_store=fake_vector_store,
        )
    assert exc.value.code == "not_found"

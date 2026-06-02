import pytest

from app.customers import collection_name
from app.ingestion import IngestionError, delete_document, ingest_text, list_documents
from app.tests.conftest import create_customer


def test_ingest_success_writes_sqlite_and_qdrant(db_session, fake_vector_store, fake_embeddings):
    create_customer(db_session, "acme", "Acme GmbH")
    text = "Dies ist ein ausreichend langer Support-Text für die Indexierung im Acme-Mandanten."

    result = ingest_text(
        db_session,
        customer_id="acme",
        title="Acme FAQ",
        text=text,
        source_type="manual",
        embeddings=fake_embeddings,
        vector_store=fake_vector_store,
    )

    assert result.document.status == "indexed"
    assert result.document.chunk_count >= 1
    assert result.document.customer_id == "acme"

    docs = list_documents(db_session, "acme")
    assert len(docs) == 1
    assert docs[0]["title"] == "Acme FAQ"

    bucket = fake_vector_store.collections[collection_name("acme")]
    assert len(bucket) == result.document.chunk_count


def test_ingest_rejects_empty_text(db_session, fake_vector_store, fake_embeddings):
    create_customer(db_session, "acme", "Acme GmbH")
    with pytest.raises(IngestionError) as exc:
        ingest_text(
            db_session,
            customer_id="acme",
            title="Leer",
            text="kurz",
            embeddings=fake_embeddings,
            vector_store=fake_vector_store,
        )
    assert exc.value.code == "empty_text"
    assert list_documents(db_session, "acme") == []


def test_embedding_failure_does_not_create_indexed_document(db_session, fake_vector_store):
    create_customer(db_session, "acme", "Acme GmbH")

    class BrokenEmbeddings:
        def embed_documents(self, texts):
            raise RuntimeError("boom")

        def embed_query(self, text):
            raise RuntimeError("boom")

    with pytest.raises(IngestionError) as exc:
        ingest_text(
            db_session,
            customer_id="acme",
            title="Fail",
            text="Dies ist ein ausreichend langer Text für den Embedding-Fehlerfall im Test.",
            embeddings=BrokenEmbeddings(),
            vector_store=fake_vector_store,
        )
    assert exc.value.code == "embedding_failed"
    assert list_documents(db_session, "acme") == []


def test_delete_document_scoped_to_customer(db_session, fake_vector_store, fake_embeddings):
    create_customer(db_session, "acme", "Acme GmbH")
    create_customer(db_session, "globex", "Globex AG")

    acme_doc = ingest_text(
        db_session,
        customer_id="acme",
        title="Acme Only",
        text="Nur Acme sichtbar — ausreichend langer Text für den Delete-Isolationstest.",
        embeddings=fake_embeddings,
        vector_store=fake_vector_store,
    ).document

    assert delete_document(db_session, "globex", acme_doc.id, vector_store=fake_vector_store) is False
    assert delete_document(db_session, "acme", acme_doc.id, vector_store=fake_vector_store) is True
    assert list_documents(db_session, "acme") == []

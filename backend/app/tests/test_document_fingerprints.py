from __future__ import annotations

import uuid

from app.document_fingerprints import (
    build_fingerprint_text,
    find_similar_documents,
    fingerprint_point_id,
    inspect_similarity_payload,
    upsert_document_fingerprint,
)
from app.ingestion import ingest_text
from app.tests.conftest import create_customer


def test_build_fingerprint_text_uses_head_and_tail_for_long_docs() -> None:
    body = ("Abschnitt. " * 800).strip()
    text = build_fingerprint_text("Policy", body)
    assert text is not None
    assert text.startswith("Titel: Policy")
    assert "..." in text
    assert len(text) < len(body)


def test_find_similar_documents_returns_high_scoring_match(db_session, fake_vector_store) -> None:
    create_customer(db_session, "acme", "Acme")
    base_text = "Dies ist ein langer Wissensinhalt über Rufbereitschaft und Vergütung mit ausreichend Zeichen."
    revised_text = (
        base_text
        + " Zusätzlich gilt ab 2026 eine neue Regelung für Wochenenddienste in der Vergütungstabelle."
    )

    ingest_text(
        db_session,
        customer_id="acme",
        title="V1.1",
        text=base_text,
    )

    near_vector = [1.0] + [0.02] * 1535
    far_vector = [0.0, 1.0] + [0.0] * 1534
    fake_vector_store.upsert(
        "acme",
        [
            (
                fingerprint_point_id("manual-near"),
                near_vector,
                {
                    "kind": "document_fingerprint",
                    "customer_id": "acme",
                    "document_id": "manual-near",
                    "title": "Near Match",
                },
            ),
            (
                fingerprint_point_id("manual-far"),
                far_vector,
                {
                    "kind": "document_fingerprint",
                    "customer_id": "acme",
                    "document_id": "manual-far",
                    "title": "Far Match",
                },
            ),
        ],
    )

    class NearEmbeddings:
        def embed_query(self, _text: str) -> list[float]:
            return near_vector

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [self.embed_query(text) for text in texts]

    # Seed a document row for the manual fingerprint hit.
    from app.models import Document, utc_now_iso

    now = utc_now_iso()
    db_session.add(
        Document(
            id="manual-near",
            customer_id="acme",
            title="Near Match",
            source_type="manual",
            chunk_count=1,
            status="indexed",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.commit()

    hits = find_similar_documents(
        db_session,
        "acme",
        revised_text,
        embeddings=NearEmbeddings(),
        vector_store=fake_vector_store,
    )
    assert len(hits) == 1
    assert hits[0].document_id == "manual-near"
    assert hits[0].score >= 0.92


def test_inspect_similarity_payload_prefers_exact_over_similar(db_session, fake_vector_store, fake_embeddings) -> None:
    create_customer(db_session, "acme", "Acme")
    text = "Identischer Wissensinhalt mit ausreichend Zeichen fuer exakte Duplikaterkennung."
    ingest_text(
        db_session,
        customer_id="acme",
        title="Original",
        text=text,
        embeddings=fake_embeddings,
        vector_store=fake_vector_store,
    )

    duplicate, similar, digest = inspect_similarity_payload(db_session, "acme", text)
    assert duplicate is not None
    assert duplicate["match"] == "exact"
    assert duplicate["title"] == "Original"
    assert similar == []
    assert digest is not None


def test_fingerprint_point_id_is_valid_uuid() -> None:
    point_id = fingerprint_point_id("doc-fp-1")
    parsed = uuid.UUID(point_id)
    assert str(parsed) == point_id
    assert fingerprint_point_id("doc-fp-1") == point_id


def test_upsert_document_fingerprint_writes_fingerprint_point(db_session, fake_vector_store, fake_embeddings) -> None:
    create_customer(db_session, "acme", "Acme")
    text = "Fingerprint Testinhalt mit genug Zeichen fuer den Document Vector."
    upsert_document_fingerprint(
        customer_id="acme",
        document_id="doc-fp-1",
        title="Fingerprint Doc",
        normalized_text=text,
        embeddings=fake_embeddings,
        vector_store=fake_vector_store,
    )
    bucket = fake_vector_store.collections["kb_acme"]
    assert fingerprint_point_id("doc-fp-1") in bucket
    assert bucket[fingerprint_point_id("doc-fp-1")][1]["kind"] == "document_fingerprint"

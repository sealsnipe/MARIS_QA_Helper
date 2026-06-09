from app.customers import collection_name
from app.ingestion import ingest_text
from app.retrieval import filter_sources_by_answer_citations, search_knowledge_base
from app.tests.conftest import create_customer


def test_search_excludes_fingerprint_points(db_session, fake_vector_store, fake_embeddings):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    document = ingest_text(
        db_session,
        customer_id="bg-ludwigshafen",
        title="Rufbereitschaft",
        text="Vergütung der 24/7-Rufbereitschaft mit genügend Zeichen für den Fingerprint-Filter-Test.",
        embeddings=fake_embeddings,
        vector_store=fake_vector_store,
    ).document

    # FakeEmbeddings liefert identische Vektoren → Fingerprint-Punkt hätte ohne
    # Filter denselben Score wie die Chunks und würde in den Treffern landen.
    bucket = fake_vector_store.collections[collection_name("bg-ludwigshafen")]
    assert any(payload.get("kind") == "document_fingerprint" for _, payload in bucket.values())

    hits = search_knowledge_base(
        "bg-ludwigshafen",
        "Vergütung Rufbereitschaft",
        top_k=10,
        min_score=0.0,
        embeddings=fake_embeddings,
        vector_store=fake_vector_store,
    )

    assert len(hits) == document.chunk_count
    assert all(hit.text.strip() for hit in hits)


def test_filter_sources_keeps_only_cited_numbers():
    sources = [
        {"n": 1, "title": "A", "chunk_index": 0, "score": 0.9},
        {"n": 2, "title": "B", "chunk_index": 1, "score": 0.8},
        {"n": 3, "title": "C", "chunk_index": 2, "score": 0.7},
    ]
    filtered = filter_sources_by_answer_citations(sources, "Die Zeiten stehen in [2].")
    assert len(filtered) == 1
    assert filtered[0]["n"] == 2
    assert filtered[0]["title"] == "B"


def test_filter_sources_without_citations_keeps_best_hit():
    sources = [
        {"n": 1, "title": "A", "chunk_index": 0, "score": 0.6},
        {"n": 2, "title": "B", "chunk_index": 1, "score": 0.9},
    ]
    filtered = filter_sources_by_answer_citations(sources, "Antwort ohne Zitat.")
    assert len(filtered) == 1
    assert filtered[0]["title"] == "B"

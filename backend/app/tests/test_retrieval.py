from app.retrieval import filter_sources_by_answer_citations


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

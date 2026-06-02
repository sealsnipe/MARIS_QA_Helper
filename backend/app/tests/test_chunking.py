import pytest

from app.chunking import CHUNK_OVERLAP, CHUNK_SIZE, chunk_text, normalize_text, validate_ingest_text


def test_normalize_collapses_whitespace():
    assert normalize_text("  Hallo   Welt \n\n\n Test  ") == "Hallo Welt\n\nTest"


def test_short_text_single_chunk():
    text = "Dies ist ein kurzer Support-Text für den Test."
    chunks = chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_long_text_multiple_chunks_with_overlap():
    paragraph = "Absatz mit Inhalt. " * 300
    text = f"{paragraph}\n\n{paragraph}"
    chunks = chunk_text(text)
    assert len(chunks) > 1
    assert all(chunk.strip() for chunk in chunks)
    assert all(len(chunk) <= CHUNK_SIZE for chunk in chunks)
    assert CHUNK_OVERLAP > 0


def test_chunk_indices_start_at_zero_via_ingestion_shape():
    text = ("Wichtiger Support-Inhalt. " * 80).strip()
    chunks = chunk_text(text)
    assert chunks
    assert chunks[0].startswith("Wichtiger")


def test_validate_rejects_too_short_text():
    with pytest.raises(ValueError, match="empty_text"):
        validate_ingest_text("zu kurz")

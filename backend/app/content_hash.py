from __future__ import annotations

import hashlib

from app.chunking import MIN_TEXT_LENGTH, normalize_text


def content_sha256_from_text(text: str) -> str | None:
    """SHA256 of normalized ingest text. Returns None if text is too short to index."""
    normalized = normalize_text(text)
    if len(normalized) < MIN_TEXT_LENGTH:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

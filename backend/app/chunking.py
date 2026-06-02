import re

CHUNK_SIZE = 3500
CHUNK_OVERLAP = 400
MIN_TEXT_LENGTH = 20


def normalize_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r" *\n *", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _split_paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n", text)
    return [part.strip() for part in parts if part.strip()]


def chunk_text(text: str, *, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []

    if len(normalized) <= chunk_size:
        return [normalized]

    paragraphs = _split_paragraphs(normalized)
    if not paragraphs:
        paragraphs = [normalized]

    chunks: list[str] = []
    current = ""

    def flush_current() -> None:
        nonlocal current
        piece = current.strip()
        if piece:
            chunks.append(piece)
        current = ""

    for paragraph in paragraphs:
        if len(paragraph) > chunk_size:
            flush_current()
            start = 0
            while start < len(paragraph):
                end = min(start + chunk_size, len(paragraph))
                chunks.append(paragraph[start:end].strip())
                if end >= len(paragraph):
                    break
                start = max(end - overlap, start + 1)
            continue

        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            flush_current()
            current = paragraph

    flush_current()

    if overlap > 0 and len(chunks) > 1:
        overlapped: list[str] = [chunks[0]]
        for index in range(1, len(chunks)):
            previous_tail = overlapped[-1][-overlap:]
            merged = f"{previous_tail}{chunks[index]}".strip()
            if len(merged) <= chunk_size:
                overlapped[-1] = merged
            else:
                overlapped.append(chunks[index])
        chunks = overlapped

    return [chunk for chunk in chunks if chunk]


def validate_ingest_text(text: str) -> str:
    normalized = normalize_text(text)
    if len(normalized) < MIN_TEXT_LENGTH:
        raise ValueError("empty_text")
    return normalized

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.chunking import MIN_TEXT_LENGTH, normalize_text
from app.config import get_settings
from app.content_hash import content_sha256_from_text
from app.embeddings import EmbeddingsBackend, get_embeddings_backend
from app.duplicates import duplicate_document_payload, find_duplicate_document
from app.models import Document
from app.qdrant_store import VectorStore, get_vector_store

FINGERPRINT_KIND = "document_fingerprint"
FINGERPRINT_HEAD_CHARS = 4000
FINGERPRINT_TAIL_CHARS = 2000
FINGERPRINT_POINT_NAMESPACE = uuid.UUID("a4f8c2e1-7b3d-5f6a-9c0d-1e2f3a4b5c6d")


def fingerprint_point_id(document_id: str) -> str:
    """Qdrant point IDs must be UUIDs or integers — not arbitrary strings like fp:…"""
    return str(uuid.uuid5(FINGERPRINT_POINT_NAMESPACE, f"document_fingerprint:{document_id}"))


def build_fingerprint_text(title: str, normalized_text: str) -> str | None:
    body = normalize_text(normalized_text)
    if len(body) < MIN_TEXT_LENGTH:
        return None
    cleaned_title = title.strip() or "Wissenseintrag"
    if len(body) <= FINGERPRINT_HEAD_CHARS + FINGERPRINT_TAIL_CHARS:
        return f"Titel: {cleaned_title}\n\n{body}"
    head = body[:FINGERPRINT_HEAD_CHARS]
    tail = body[-FINGERPRINT_TAIL_CHARS:]
    return f"Titel: {cleaned_title}\n\n{head}\n\n...\n\n{tail}"


def upsert_document_fingerprint(
    *,
    customer_id: str,
    document_id: str,
    title: str,
    normalized_text: str,
    embeddings: EmbeddingsBackend | None = None,
    vector_store: VectorStore | None = None,
) -> None:
    fingerprint_text = build_fingerprint_text(title, normalized_text)
    if fingerprint_text is None:
        return

    embeddings = embeddings or get_embeddings_backend()
    vector_store = vector_store or get_vector_store()
    vector = embeddings.embed_query(fingerprint_text)
    payload = {
        "kind": FINGERPRINT_KIND,
        "customer_id": customer_id,
        "document_id": document_id,
        "title": title.strip() or "Wissenseintrag",
    }
    vector_store.upsert(
        customer_id,
        [(fingerprint_point_id(document_id), vector, payload)],
    )


@dataclass
class SimilarDocumentHit:
    document_id: str
    title: str
    created_at: str
    score: float


def similar_document_payload(hit: SimilarDocumentHit) -> dict:
    return {
        "document_id": hit.document_id,
        "title": hit.title,
        "created_at": hit.created_at,
        "score": round(hit.score, 4),
        "match": "similar",
    }


def find_similar_documents(
    db: Session,
    customer_id: str,
    text: str,
    *,
    exclude_document_ids: set[str] | None = None,
    embeddings: EmbeddingsBackend | None = None,
    vector_store: VectorStore | None = None,
) -> list[SimilarDocumentHit]:
    settings = get_settings()
    fingerprint_text = build_fingerprint_text("Upload", text)
    if fingerprint_text is None:
        return []

    embeddings = embeddings or get_embeddings_backend()
    vector_store = vector_store or get_vector_store()
    vector = embeddings.embed_query(fingerprint_text)
    raw_hits = vector_store.search_fingerprints(
        customer_id,
        vector,
        settings.DUPLICATE_SIMILAR_TOP_K,
    )

    excluded = set(exclude_document_ids or [])
    exact = find_duplicate_document(db, customer_id, text)
    if exact is not None:
        excluded.add(exact.id)

    results: list[SimilarDocumentHit] = []
    for hit in raw_hits:
        if hit.score < settings.DUPLICATE_SIMILAR_MIN_SCORE:
            continue
        document_id = str(hit.payload.get("document_id") or "")
        if not document_id or document_id in excluded:
            continue
        document = db.get(Document, document_id)
        if document is None or document.deleted_at is not None:
            continue
        if document.customer_id != customer_id:
            continue
        results.append(
            SimilarDocumentHit(
                document_id=document.id,
                title=document.title,
                created_at=document.created_at,
                score=hit.score,
            )
        )
    return results


def inspect_similarity_payload(
    db: Session,
    customer_id: str,
    text: str,
) -> tuple[dict | None, list[dict], str | None]:
    """Returns (duplicate, similar[], content_sha256) for inspect responses."""
    digest = content_sha256_from_text(text)
    duplicate_doc = find_duplicate_document(db, customer_id, text)
    duplicate = None
    exclude_ids: set[str] = set()
    if duplicate_doc is not None:
        duplicate = duplicate_document_payload(duplicate_doc)
        duplicate["match"] = "exact"
        exclude_ids.add(duplicate_doc.id)

    similar_hits = find_similar_documents(
        db,
        customer_id,
        text,
        exclude_document_ids=exclude_ids,
    )
    similar = [similar_document_payload(item) for item in similar_hits]
    return duplicate, similar, digest

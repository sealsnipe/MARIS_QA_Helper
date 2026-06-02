from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.chunking import chunk_text, validate_ingest_text
from app.embeddings import EmbeddingsBackend, get_embeddings_backend
from app.models import Chunk, Document, utc_now_iso
from app.qdrant_store import VectorStore, get_vector_store


class IngestionError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


@dataclass
class IngestResult:
    document: Document


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _document_to_dict(document: Document) -> dict[str, Any]:
    return {
        "id": document.id,
        "customer_id": document.customer_id,
        "title": document.title,
        "source_type": document.source_type,
        "original_filename": document.original_filename,
        "mime_type": document.mime_type,
        "chunk_count": document.chunk_count,
        "status": document.status,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }


def ingest_text(
    db: Session,
    customer_id: str,
    title: str,
    text: str,
    source_type: str = "manual",
    *,
    document_id: str | None = None,
    original_filename: str | None = None,
    mime_type: str | None = None,
    storage_path: str | None = None,
    source_url: str | None = None,
    external_id: str | None = None,
    embeddings: EmbeddingsBackend | None = None,
    vector_store: VectorStore | None = None,
) -> IngestResult:
    cleaned_title = title.strip()
    if not cleaned_title or len(cleaned_title) > 200:
        raise IngestionError("invalid_title")

    try:
        normalized = validate_ingest_text(text)
    except ValueError as exc:
        raise IngestionError(str(exc)) from exc

    pieces = chunk_text(normalized)
    if not pieces:
        raise IngestionError("empty_text")

    embeddings = embeddings or get_embeddings_backend()
    vector_store = vector_store or get_vector_store()

    document_id = document_id or str(uuid.uuid4())
    now = utc_now_iso()
    document = Document(
        id=document_id,
        customer_id=customer_id,
        title=cleaned_title,
        source_type=source_type,
        source_url=source_url,
        external_id=external_id,
        original_filename=original_filename,
        mime_type=mime_type,
        storage_path=storage_path,
        chunk_count=0,
        status="indexed",
        created_at=now,
        updated_at=now,
    )

    try:
        vectors = embeddings.embed_documents(pieces)
    except Exception as exc:
        raise IngestionError("embedding_failed", detail=str(exc)) from exc

    if len(vectors) != len(pieces):
        raise IngestionError("embedding_failed")

    points: list[tuple[str, list[float], dict[str, Any]]] = []
    chunk_rows: list[Chunk] = []

    for index, (piece, vector) in enumerate(zip(pieces, vectors, strict=True)):
        chunk_id = str(uuid.uuid4())
        payload = {
            "customer_id": customer_id,
            "document_id": document_id,
            "chunk_id": chunk_id,
            "chunk_index": index,
            "title": cleaned_title,
            "source_type": source_type,
            "source_url": source_url,
            "text": piece,
        }
        points.append((chunk_id, vector, payload))
        chunk_rows.append(
            Chunk(
                id=chunk_id,
                document_id=document_id,
                customer_id=customer_id,
                chunk_index=index,
                text=piece,
                token_estimate=_estimate_tokens(piece),
                qdrant_point_id=chunk_id,
                created_at=now,
            )
        )

    try:
        vector_store.ensure_collection(customer_id)
        vector_store.upsert(customer_id, points)
    except Exception as exc:
        try:
            vector_store.delete_document(customer_id, document_id)
        except Exception:
            pass
        raise IngestionError("vector_store_failed", detail=str(exc)) from exc

    document.chunk_count = len(chunk_rows)
    db.add(document)
    db.add_all(chunk_rows)
    db.commit()
    db.refresh(document)
    return IngestResult(document=document)


def list_documents_for_customers(db: Session, customer_ids: list[str]) -> list[dict[str, Any]]:
    if not customer_ids:
        return []
    stmt = (
        select(Document)
        .where(Document.customer_id.in_(customer_ids), Document.deleted_at.is_(None))
        .order_by(Document.created_at.desc())
    )
    rows = list(db.scalars(stmt))
    return [_document_to_dict(row) for row in rows]


def list_documents(db: Session, customer_id: str) -> list[dict[str, Any]]:
    stmt = (
        select(Document)
        .where(Document.customer_id == customer_id, Document.deleted_at.is_(None))
        .order_by(Document.created_at.desc())
    )
    rows = list(db.scalars(stmt))
    return [_document_to_dict(row) for row in rows]


def delete_document(
    db: Session,
    customer_id: str,
    document_id: str,
    *,
    vector_store: VectorStore | None = None,
) -> bool:
    document = db.get(Document, document_id)
    if document is None or document.deleted_at is not None:
        return False
    if document.customer_id != customer_id:
        return False

    store = vector_store or get_vector_store()
    store.delete_document(customer_id, document_id)
    document.deleted_at = utc_now_iso()
    document.updated_at = document.deleted_at
    db.commit()
    return True

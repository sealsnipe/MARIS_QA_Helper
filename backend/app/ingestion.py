from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, select
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


def _parse_extraction_meta(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


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
        "extraction_meta": _parse_extraction_meta(document.extraction_meta),
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }


def _build_chunk_rows_and_points(
    *,
    customer_id: str,
    document_id: str,
    title: str,
    pieces: list[str],
    vectors: list[list[float]],
    source_type: str,
    source_url: str | None,
    created_at: str,
) -> tuple[list[tuple[str, list[float], dict[str, Any]]], list[Chunk]]:
    points: list[tuple[str, list[float], dict[str, Any]]] = []
    chunk_rows: list[Chunk] = []
    for index, (piece, vector) in enumerate(zip(pieces, vectors, strict=True)):
        chunk_id = str(uuid.uuid4())
        payload = {
            "customer_id": customer_id,
            "document_id": document_id,
            "chunk_id": chunk_id,
            "chunk_index": index,
            "title": title,
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
                created_at=created_at,
            )
        )
    return points, chunk_rows


def _upsert_vectors(
    vector_store: VectorStore,
    customer_id: str,
    document_id: str,
    points: list[tuple[str, list[float], dict[str, Any]]],
) -> None:
    try:
        vector_store.ensure_collection(customer_id)
        vector_store.upsert(customer_id, points)
    except Exception as exc:
        try:
            vector_store.delete_document(customer_id, document_id)
        except Exception:
            pass
        raise IngestionError("vector_store_failed", detail=str(exc)) from exc


def get_document(db: Session, customer_id: str, document_id: str) -> Document | None:
    document = db.get(Document, document_id)
    if document is None or document.deleted_at is not None:
        return None
    if document.customer_id != customer_id:
        return None
    return document


def _reconstruct_text_from_chunks(document: Document) -> str:
    chunks = sorted(document.chunks, key=lambda row: row.chunk_index)
    if not chunks:
        return ""
    return "\n\n".join(chunk.text for chunk in chunks if chunk.text.strip())


def get_document_text(db: Session, customer_id: str, document_id: str) -> tuple[Document, str] | None:
    document = get_document(db, customer_id, document_id)
    if document is None:
        return None
    if document.source_text and document.source_text.strip():
        return document, document.source_text
    return document, _reconstruct_text_from_chunks(document)


def _embed_pieces(embeddings: EmbeddingsBackend, pieces: list[str]) -> list[list[float]]:
    try:
        vectors = embeddings.embed_documents(pieces)
    except Exception as exc:
        raise IngestionError("embedding_failed", detail=str(exc)) from exc
    if len(vectors) != len(pieces):
        raise IngestionError("embedding_failed")
    return vectors


def _index_document_chunks(
    db: Session,
    document: Document,
    *,
    title: str,
    normalized_text: str,
    pieces: list[str],
    embeddings: EmbeddingsBackend,
    vector_store: VectorStore,
    now: str,
    source_type: str | None = None,
    vectors: list[list[float]] | None = None,
) -> Document:
    if vectors is None:
        vectors = _embed_pieces(embeddings, pieces)

    effective_source_type = source_type if source_type is not None else document.source_type
    points, chunk_rows = _build_chunk_rows_and_points(
        customer_id=document.customer_id,
        document_id=document.id,
        title=title,
        pieces=pieces,
        vectors=vectors,
        source_type=effective_source_type,
        source_url=document.source_url,
        created_at=now,
    )
    _upsert_vectors(vector_store, document.customer_id, document.id, points)

    document.title = title
    document.source_text = normalized_text
    document.source_type = effective_source_type
    document.chunk_count = len(chunk_rows)
    document.status = "indexed"
    document.error_message = None
    document.updated_at = now
    db.add_all(chunk_rows)
    return document


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
    extraction_meta: str | None = None,
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
        source_text=normalized,
        extraction_meta=extraction_meta,
        chunk_count=0,
        status="indexed",
        created_at=now,
        updated_at=now,
    )
    db.add(document)
    db.flush()

    try:
        _index_document_chunks(
            db,
            document,
            title=cleaned_title,
            normalized_text=normalized,
            pieces=pieces,
            embeddings=embeddings,
            vector_store=vector_store,
            now=now,
        )
    except IngestionError:
        db.rollback()
        raise
    db.commit()
    db.refresh(document)
    return IngestResult(document=document)


def update_document_content(
    db: Session,
    customer_id: str,
    document_id: str,
    title: str,
    text: str,
    *,
    embeddings: EmbeddingsBackend | None = None,
    vector_store: VectorStore | None = None,
) -> IngestResult:
    document = get_document(db, customer_id, document_id)
    if document is None:
        raise IngestionError("not_found")

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
    now = utc_now_iso()

    had_file_origin = document.storage_path is not None and document.source_type != "manual"
    new_source_type = "manual" if had_file_origin else document.source_type

    vectors = _embed_pieces(embeddings, pieces)
    vector_store.delete_document(customer_id, document_id)
    db.execute(delete(Chunk).where(Chunk.document_id == document_id))

    _index_document_chunks(
        db,
        document,
        title=cleaned_title,
        normalized_text=normalized,
        pieces=pieces,
        embeddings=embeddings,
        vector_store=vector_store,
        now=now,
        source_type=new_source_type,
        vectors=vectors,
    )
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

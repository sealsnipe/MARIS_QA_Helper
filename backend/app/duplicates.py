from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.content_hash import content_sha256_from_text
from app.models import Document


def duplicate_document_payload(document: Document) -> dict[str, str]:
    return {
        "document_id": document.id,
        "title": document.title,
        "created_at": document.created_at,
    }


def find_duplicate_document(
    db: Session,
    customer_id: str,
    text: str,
    *,
    exclude_document_id: str | None = None,
) -> Document | None:
    digest = content_sha256_from_text(text)
    if digest is None:
        return None
    stmt = select(Document).where(
        Document.customer_id == customer_id,
        Document.content_sha256 == digest,
        Document.deleted_at.is_(None),
    )
    if exclude_document_id:
        stmt = stmt.where(Document.id != exclude_document_id)
    return db.scalars(stmt).first()

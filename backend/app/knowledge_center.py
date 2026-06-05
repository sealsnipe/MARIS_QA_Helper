from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.chunking import validate_ingest_text
from app.customers import (
    GLOBAL_CUSTOMER_ID,
    get_customer,
    is_customer_active,
    is_global_customer,
    list_effective_tenant_customers_for_user,
    user_has_customer,
    validate_customer_slug,
)
from app.ingestion import IngestionError, ingest_text
from app.models import KnowledgeContent, KnowledgeSource, User, utc_now_iso

CONTENT_STATUS_PENDING = "pending"
CONTENT_STATUS_ADOPTED = "adopted"
CONTENT_STATUS_REJECTED = "rejected"
CONTENT_STATUSES = frozenset({CONTENT_STATUS_PENDING, CONTENT_STATUS_ADOPTED, CONTENT_STATUS_REJECTED})


class KnowledgeCenterError(Exception):
    def __init__(self, code: str, *, status_code: int = 400, detail: str = "") -> None:
        self.code = code
        self.status_code = status_code
        self.detail = detail
        super().__init__(code)


def _validate_host_code(host_code: str) -> str:
    slug = host_code.strip().lower()
    if not validate_customer_slug(slug):
        raise KnowledgeCenterError("invalid_host_code")
    return slug


def _validate_source_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned or len(cleaned) > 120:
        raise KnowledgeCenterError("invalid_name")
    return cleaned


def _normalize_keywords(raw: list[str] | str | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = [part.strip() for part in raw.split(",")]
        return [part for part in parts if part]
    return [str(item).strip() for item in raw if str(item).strip()]


def _keywords_to_json(keywords: list[str]) -> str:
    return json.dumps(keywords, ensure_ascii=False)


def _keywords_from_json(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]
    return []


def source_to_dict(source: KnowledgeSource) -> dict:
    return {
        "id": source.id,
        "name": source.name,
        "host_code": source.host_code,
        "active": bool(source.active),
        "created_at": source.created_at,
        "updated_at": source.updated_at,
    }


def content_to_dict(db: Session, content: KnowledgeContent) -> dict:
    source = db.get(KnowledgeSource, content.source_id)
    suggested = (
        get_customer(db, content.suggested_customer_id) if content.suggested_customer_id else None
    )
    adopted = get_customer(db, content.adopted_customer_id) if content.adopted_customer_id else None
    return {
        "id": content.id,
        "source_id": content.source_id,
        "source_name": source.name if source else "",
        "host_code": source.host_code if source else "",
        "suggested_customer_id": content.suggested_customer_id,
        "suggested_customer_name": suggested.name if suggested else None,
        "title": content.title,
        "summary": content.summary,
        "keywords": _keywords_from_json(content.keywords_json),
        "content": content.content,
        "source_ref": content.source_ref,
        "external_id": content.external_id,
        "status": content.status,
        "adopted_customer_id": content.adopted_customer_id,
        "adopted_customer_name": adopted.name if adopted else None,
        "adopted_document_id": content.adopted_document_id,
        "reviewed_by": content.reviewed_by,
        "reviewed_at": content.reviewed_at,
        "created_at": content.created_at,
        "received_at": content.received_at,
    }


def list_knowledge_sources(db: Session) -> list[dict]:
    rows = list(db.scalars(select(KnowledgeSource).order_by(KnowledgeSource.name)))
    return [source_to_dict(row) for row in rows]


def get_source_by_host_code(db: Session, host_code: str) -> KnowledgeSource | None:
    slug = host_code.strip().lower()
    if not slug:
        return None
    return db.scalar(select(KnowledgeSource).where(KnowledgeSource.host_code == slug))


def create_knowledge_source(db: Session, name: str, host_code: str) -> KnowledgeSource:
    display_name = _validate_source_name(name)
    slug = _validate_host_code(host_code)
    if get_source_by_host_code(db, slug) is not None:
        raise KnowledgeCenterError("source_exists", status_code=409)

    now = utc_now_iso()
    row = KnowledgeSource(
        id=str(uuid.uuid4()),
        name=display_name,
        host_code=slug,
        active=1,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_knowledge_source(
    db: Session,
    source_id: str,
    *,
    name: str | None = None,
    active: bool | None = None,
) -> KnowledgeSource:
    row = db.get(KnowledgeSource, source_id)
    if row is None:
        raise KnowledgeCenterError("not_found", status_code=404)

    changed = False
    if name is not None:
        row.name = _validate_source_name(name)
        changed = True
    if active is not None:
        row.active = 1 if active else 0
        changed = True
    if changed:
        row.updated_at = utc_now_iso()
        db.commit()
        db.refresh(row)
    return row


def delete_knowledge_source(db: Session, source_id: str) -> None:
    row = db.get(KnowledgeSource, source_id)
    if row is None:
        raise KnowledgeCenterError("not_found", status_code=404)
    linked = db.scalar(
        select(KnowledgeContent.id).where(KnowledgeContent.source_id == source_id).limit(1)
    )
    if linked is not None:
        raise KnowledgeCenterError("source_has_contents", status_code=409)
    db.delete(row)
    db.commit()


def _visible_customer_ids(db: Session, user: User) -> set[str]:
    return {customer.id for customer in list_effective_tenant_customers_for_user(db, user)}


def _content_visible_to_user(db: Session, user: User, content: KnowledgeContent) -> bool:
    visible_ids = _visible_customer_ids(db, user)
    if not visible_ids:
        return False
    if content.suggested_customer_id is None:
        return True
    return content.suggested_customer_id in visible_ids


def _content_visibility_filter(user: User, visible_ids: set[str]):
    if not visible_ids:
        return KnowledgeContent.id.is_(None)
    return or_(
        KnowledgeContent.suggested_customer_id.is_(None),
        KnowledgeContent.suggested_customer_id.in_(visible_ids),
    )


def list_knowledge_contents(
    db: Session,
    user: User,
    *,
    status: str | None = CONTENT_STATUS_PENDING,
    source_id: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    visible_ids = _visible_customer_ids(db, user)
    if not visible_ids:
        return [], 0

    stmt = select(KnowledgeContent).where(_content_visibility_filter(user, visible_ids))
    if status:
        if status not in CONTENT_STATUSES:
            raise KnowledgeCenterError("invalid_status")
        stmt = stmt.where(KnowledgeContent.status == status)
    if source_id:
        stmt = stmt.where(KnowledgeContent.source_id == source_id)
    if search:
        needle = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                KnowledgeContent.title.ilike(needle),
                KnowledgeContent.summary.ilike(needle),
                KnowledgeContent.content.ilike(needle),
            )
        )

    total = len(list(db.scalars(stmt)))
    rows = list(
        db.scalars(
            stmt.order_by(KnowledgeContent.received_at.desc()).offset(offset).limit(limit)
        )
    )
    return [content_to_dict(db, row) for row in rows], total


def get_knowledge_content_for_user(db: Session, user: User, content_id: str) -> KnowledgeContent:
    row = db.get(KnowledgeContent, content_id)
    if row is None:
        raise KnowledgeCenterError("not_found", status_code=404)
    if not _content_visible_to_user(db, user, row):
        raise KnowledgeCenterError("forbidden", status_code=403)
    return row


def _validate_content_item_fields(item: dict[str, Any]) -> dict[str, Any]:
    title = str(item.get("title", "")).strip()
    if not title or len(title) > 200:
        raise KnowledgeCenterError("invalid_title")

    summary = str(item.get("summary", "")).strip()
    if len(summary) > 2000:
        raise KnowledgeCenterError("invalid_summary")

    content_text = str(item.get("content", "")).strip()
    try:
        validate_ingest_text(content_text)
    except ValueError as exc:
        raise KnowledgeCenterError(str(exc)) from exc

    keywords = _normalize_keywords(item.get("keywords"))
    source_ref = str(item.get("source_ref", "")).strip() or None
    external_id = str(item.get("external_id", "")).strip() or None
    if external_id and len(external_id) > 200:
        raise KnowledgeCenterError("invalid_external_id")

    customer_id = item.get("customer_id")
    suggested_customer_id: str | None = None
    if customer_id is not None:
        slug = str(customer_id).strip().lower()
        if slug:
            if is_global_customer(slug):
                raise KnowledgeCenterError("forbidden_customer", status_code=403)
            if not validate_customer_slug(slug):
                raise KnowledgeCenterError("invalid_customer_id")
            suggested_customer_id = slug

    return {
        "title": title,
        "summary": summary,
        "content": content_text,
        "keywords": keywords,
        "source_ref": source_ref,
        "external_id": external_id,
        "suggested_customer_id": suggested_customer_id,
    }


def ingest_knowledge_contents(
    db: Session,
    host_code: str,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    if not items:
        raise KnowledgeCenterError("empty_batch")

    source = get_source_by_host_code(db, host_code.strip().lower())
    if source is None:
        raise KnowledgeCenterError("unknown_source", status_code=400)
    if not source.active:
        raise KnowledgeCenterError("source_inactive", status_code=403)

    created = 0
    updated = 0
    skipped = 0
    errors: list[dict[str, str]] = []

    for index, raw_item in enumerate(items):
        try:
            fields = _validate_content_item_fields(raw_item)
        except KnowledgeCenterError as exc:
            errors.append({"index": str(index), "error": exc.code, "detail": exc.detail})
            continue

        if fields["suggested_customer_id"]:
            customer = get_customer(db, fields["suggested_customer_id"])
            if customer is None or not is_customer_active(customer) or is_global_customer(customer.id):
                errors.append({"index": str(index), "error": "unknown_customer"})
                continue

        existing: KnowledgeContent | None = None
        if fields["external_id"]:
            existing = db.scalar(
                select(KnowledgeContent).where(
                    KnowledgeContent.source_id == source.id,
                    KnowledgeContent.external_id == fields["external_id"],
                )
            )

        now = utc_now_iso()
        if existing is not None:
            if existing.status != CONTENT_STATUS_PENDING:
                skipped += 1
                continue
            existing.title = fields["title"]
            existing.summary = fields["summary"]
            existing.content = fields["content"]
            existing.keywords_json = _keywords_to_json(fields["keywords"])
            existing.source_ref = fields["source_ref"]
            existing.suggested_customer_id = fields["suggested_customer_id"]
            existing.received_at = now
            updated += 1
        else:
            db.add(
                KnowledgeContent(
                    id=str(uuid.uuid4()),
                    source_id=source.id,
                    suggested_customer_id=fields["suggested_customer_id"],
                    title=fields["title"],
                    summary=fields["summary"],
                    keywords_json=_keywords_to_json(fields["keywords"]),
                    content=fields["content"],
                    source_ref=fields["source_ref"],
                    external_id=fields["external_id"],
                    status=CONTENT_STATUS_PENDING,
                    created_at=now,
                    received_at=now,
                )
            )
            created += 1

    db.commit()
    return {"created": created, "updated": updated, "skipped": skipped, "errors": errors}


def adopt_knowledge_content(
    db: Session,
    user: User,
    content_id: str,
    customer_id: str,
) -> dict:
    row = get_knowledge_content_for_user(db, user, content_id)
    if row.status != CONTENT_STATUS_PENDING:
        raise KnowledgeCenterError("invalid_status", status_code=409)

    slug = customer_id.strip().lower()
    if is_global_customer(slug):
        raise KnowledgeCenterError("forbidden_customer", status_code=403)
    if not user_has_customer(db, user.id, slug):
        raise KnowledgeCenterError("forbidden_customer", status_code=403)

    source = db.get(KnowledgeSource, row.source_id)
    host_code = source.host_code if source else "unknown"

    try:
        result = ingest_text(
            db,
            slug,
            row.title,
            row.content,
            source_type=f"kc:{host_code}",
            external_id=row.external_id,
            source_url=row.source_ref,
        )
    except IngestionError as exc:
        raise KnowledgeCenterError(exc.code, status_code=400, detail=exc.detail or "") from exc

    now = utc_now_iso()
    row.status = CONTENT_STATUS_ADOPTED
    row.adopted_customer_id = slug
    row.adopted_document_id = result.document.id
    row.reviewed_by = user.id
    row.reviewed_at = now
    db.commit()
    db.refresh(row)
    return {
        "content": content_to_dict(db, row),
        "document_id": result.document.id,
        "customer_id": slug,
    }


def reject_knowledge_content(db: Session, user: User, content_id: str) -> dict:
    row = get_knowledge_content_for_user(db, user, content_id)
    if row.status != CONTENT_STATUS_PENDING:
        raise KnowledgeCenterError("invalid_status", status_code=409)

    row.status = CONTENT_STATUS_REJECTED
    row.reviewed_by = user.id
    row.reviewed_at = utc_now_iso()
    db.commit()
    db.refresh(row)
    return {"content": content_to_dict(db, row)}


def list_adoptable_customers(db: Session, user: User) -> list[dict]:
    return [
        {"id": customer.id, "name": customer.name}
        for customer in list_effective_tenant_customers_for_user(db, user)
        if customer.id != GLOBAL_CUSTOMER_ID
    ]

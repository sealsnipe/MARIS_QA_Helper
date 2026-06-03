from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.customers import get_customer, is_global_customer, list_tenant_customers, validate_customer_slug
from app.models import User, UserCustomer, utc_now_iso


class UserAdminError(Exception):
    def __init__(self, code: str, *, status_code: int = 400, detail: str = "") -> None:
        self.code = code
        self.status_code = status_code
        self.detail = detail
        super().__init__(code)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def user_to_dict(db: Session, user: User) -> dict:
    customer_ids = list(
        db.scalars(select(UserCustomer.customer_id).where(UserCustomer.user_id == user.id))
    )
    return {
        "id": user.id,
        "email": user.email,
        "is_admin": bool(user.is_admin),
        "is_active": bool(user.is_active),
        "customer_ids": customer_ids,
        "created_at": user.created_at,
    }


def list_admin_users(db: Session) -> list[dict]:
    rows = list(db.scalars(select(User).order_by(User.email)))
    return [user_to_dict(db, row) for row in rows]


def _validate_customer_ids(db: Session, customer_ids: list[str]) -> list[str]:
    slugs: list[str] = []
    for raw in customer_ids:
        slug = raw.strip().lower()
        if not slug:
            continue
        if is_global_customer(slug):
            raise UserAdminError("forbidden_customer", status_code=403)
        if not validate_customer_slug(slug):
            raise UserAdminError("invalid_customer_id")
        customer = get_customer(db, slug)
        if customer is None:
            raise UserAdminError("unknown_customer", status_code=404, detail=slug)
        slugs.append(slug)
    return slugs


def _set_memberships(db: Session, user_id: str, customer_ids: list[str]) -> None:
    db.execute(delete(UserCustomer).where(UserCustomer.user_id == user_id))
    for customer_id in customer_ids:
        db.add(UserCustomer(user_id=user_id, customer_id=customer_id))


def create_admin_user(
    db: Session,
    email: str,
    password: str,
    customer_ids: list[str],
    *,
    is_admin: bool = False,
) -> User:
    normalized = _normalize_email(email)
    if not normalized or "@" not in normalized:
        raise UserAdminError("invalid_email")
    if len(password) < 8:
        raise UserAdminError("invalid_password")
    if db.scalar(select(User).where(User.email == normalized)) is not None:
        raise UserAdminError("user_exists", status_code=409)

    slugs = _validate_customer_ids(db, customer_ids)
    row = User(
        id=str(uuid.uuid4()),
        email=normalized,
        password_hash=hash_password(password),
        is_active=1,
        is_admin=1 if is_admin else 0,
        created_at=utc_now_iso(),
    )
    db.add(row)
    db.flush()
    _set_memberships(db, row.id, slugs)
    db.commit()
    db.refresh(row)
    return row


def update_admin_user(
    db: Session,
    user_id: str,
    *,
    actor_id: str,
    email: str | None = None,
    password: str | None = None,
    customer_ids: list[str] | None = None,
    is_admin: bool | None = None,
    is_active: bool | None = None,
) -> User:
    row = db.get(User, user_id)
    if row is None:
        raise UserAdminError("not_found", status_code=404)

    if email is not None:
        normalized = _normalize_email(email)
        if not normalized or "@" not in normalized:
            raise UserAdminError("invalid_email")
        existing = db.scalar(select(User).where(User.email == normalized, User.id != user_id))
        if existing is not None:
            raise UserAdminError("user_exists", status_code=409)
        row.email = normalized

    if password is not None:
        if len(password) < 8:
            raise UserAdminError("invalid_password")
        row.password_hash = hash_password(password)

    if is_admin is not None:
        if user_id == actor_id and not is_admin:
            raise UserAdminError("cannot_demote_self", status_code=403)
        row.is_admin = 1 if is_admin else 0

    if is_active is not None:
        if user_id == actor_id and not is_active:
            raise UserAdminError("cannot_deactivate_self", status_code=403)
        row.is_active = 1 if is_active else 0

    if customer_ids is not None:
        slugs = _validate_customer_ids(db, customer_ids)
        _set_memberships(db, user_id, slugs)

    db.commit()
    db.refresh(row)
    return row


def deactivate_admin_user(db: Session, user_id: str, *, actor_id: str) -> None:
    if user_id == actor_id:
        raise UserAdminError("cannot_deactivate_self", status_code=403)
    row = db.get(User, user_id)
    if row is None:
        raise UserAdminError("not_found", status_code=404)
    row.is_active = 0
    db.commit()


def list_assignable_customers(db: Session) -> list[dict]:
    return [{"id": c.id, "name": c.name} for c in list_tenant_customers(db)]

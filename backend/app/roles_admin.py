from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Role, RoleCustomer, User, UserCustomer, UserRole, utc_now_iso


class RoleAdminError(Exception):
    def __init__(self, code: str, *, status_code: int = 400, detail: str = "") -> None:
        self.code = code
        self.status_code = status_code
        self.detail = detail
        super().__init__(code)


def _role_customer_ids(db: Session, role_id: str) -> list[str]:
    return list(
        db.scalars(select(RoleCustomer.customer_id).where(RoleCustomer.role_id == role_id))
    )


def _validate_customer_ids(db: Session, customer_ids: list[str]) -> list[str]:
    from app.customers import get_customer, is_global_customer, validate_customer_slug

    slugs: list[str] = []
    for raw in customer_ids:
        slug = raw.strip().lower()
        if not slug:
            continue
        if is_global_customer(slug):
            raise RoleAdminError("forbidden_customer", status_code=403)
        if not validate_customer_slug(slug):
            raise RoleAdminError("invalid_customer_id")
        customer = get_customer(db, slug)
        if customer is None:
            raise RoleAdminError("unknown_customer", status_code=404, detail=slug)
        slugs.append(slug)
    return slugs


def role_to_dict(db: Session, role: Role) -> dict:
    return {
        "id": role.id,
        "name": role.name,
        "is_admin": bool(role.is_admin),
        "auto_add_new_customers": bool(role.auto_add_new_customers),
        "customer_ids": _role_customer_ids(db, role.id),
        "created_at": role.created_at,
    }


def list_admin_roles(db: Session) -> list[dict]:
    rows = list(db.scalars(select(Role).order_by(Role.name)))
    return [role_to_dict(db, row) for row in rows]


def _set_role_customers(db: Session, role_id: str, customer_ids: list[str]) -> None:
    db.execute(delete(RoleCustomer).where(RoleCustomer.role_id == role_id))
    for customer_id in customer_ids:
        db.add(RoleCustomer(role_id=role_id, customer_id=customer_id))


def _validate_role_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise RoleAdminError("invalid_name")
    if len(cleaned) > 120:
        raise RoleAdminError("invalid_name")
    return cleaned


def merge_role_preset(db: Session, role_ids: list[str]) -> tuple[bool, list[str]]:
    admin = False
    customers: set[str] = set()
    for role_id in role_ids:
        role = db.get(Role, role_id)
        if role is None:
            raise RoleAdminError("unknown_role", status_code=404, detail=role_id)
        admin = admin or bool(role.is_admin)
        customers.update(_role_customer_ids(db, role.id))
    return admin, sorted(customers)


def set_user_roles(db: Session, user_id: str, role_ids: list[str]) -> None:
    unique_ids: list[str] = []
    seen: set[str] = set()
    for role_id in role_ids:
        cleaned = role_id.strip()
        if not cleaned or cleaned in seen:
            continue
        if db.get(Role, cleaned) is None:
            raise RoleAdminError("unknown_role", status_code=404, detail=cleaned)
        seen.add(cleaned)
        unique_ids.append(cleaned)

    db.execute(delete(UserRole).where(UserRole.user_id == user_id))
    for role_id in unique_ids:
        db.add(UserRole(user_id=user_id, role_id=role_id))


def list_user_role_ids(db: Session, user_id: str) -> list[str]:
    return list(
        db.scalars(select(UserRole.role_id).where(UserRole.user_id == user_id).order_by(UserRole.role_id))
    )


def create_admin_role(
    db: Session,
    name: str,
    customer_ids: list[str],
    *,
    is_admin: bool = False,
    auto_add_new_customers: bool = False,
) -> Role:
    display_name = _validate_role_name(name)
    if db.scalar(select(Role).where(Role.name == display_name)) is not None:
        raise RoleAdminError("role_exists", status_code=409)

    slugs = _validate_customer_ids(db, customer_ids)
    row = Role(
        id=str(uuid.uuid4()),
        name=display_name,
        is_admin=1 if is_admin else 0,
        auto_add_new_customers=1 if auto_add_new_customers else 0,
        created_at=utc_now_iso(),
    )
    db.add(row)
    db.flush()
    _set_role_customers(db, row.id, slugs)
    db.commit()
    db.refresh(row)
    return row


def update_admin_role(
    db: Session,
    role_id: str,
    *,
    name: str | None = None,
    customer_ids: list[str] | None = None,
    is_admin: bool | None = None,
    auto_add_new_customers: bool | None = None,
) -> Role:
    row = db.get(Role, role_id)
    if row is None:
        raise RoleAdminError("not_found", status_code=404)

    if name is not None:
        display_name = _validate_role_name(name)
        existing = db.scalar(select(Role).where(Role.name == display_name, Role.id != role_id))
        if existing is not None:
            raise RoleAdminError("role_exists", status_code=409)
        row.name = display_name

    if is_admin is not None:
        row.is_admin = 1 if is_admin else 0

    if auto_add_new_customers is not None:
        row.auto_add_new_customers = 1 if auto_add_new_customers else 0

    if customer_ids is not None:
        slugs = _validate_customer_ids(db, customer_ids)
        _set_role_customers(db, role_id, slugs)

    db.commit()
    db.refresh(row)
    return row


def delete_admin_role(db: Session, role_id: str) -> None:
    row = db.get(Role, role_id)
    if row is None:
        raise RoleAdminError("not_found", status_code=404)
    db.execute(delete(UserRole).where(UserRole.role_id == role_id))
    db.execute(delete(RoleCustomer).where(RoleCustomer.role_id == role_id))
    db.delete(row)
    db.commit()


def assign_new_customer_to_auto_roles(db: Session, customer_id: str) -> None:
    from app.customers import get_customer, is_global_customer

    if is_global_customer(customer_id):
        return
    customer = get_customer(db, customer_id)
    if customer is None:
        return

    auto_roles = list(
        db.scalars(select(Role).where(Role.auto_add_new_customers == 1))
    )
    if not auto_roles:
        return

    for role in auto_roles:
        link = db.get(RoleCustomer, {"role_id": role.id, "customer_id": customer_id})
        if link is None:
            db.add(RoleCustomer(role_id=role.id, customer_id=customer_id))

        user_ids = list(
            db.scalars(select(UserRole.user_id).where(UserRole.role_id == role.id))
        )
        for user_id in user_ids:
            user = db.get(User, user_id)
            if user is None or not user.is_active:
                continue
            membership = db.get(UserCustomer, {"user_id": user_id, "customer_id": customer_id})
            if membership is None:
                db.add(UserCustomer(user_id=user_id, customer_id=customer_id))
                db.flush()  # make it visible to subsequent iterations (same user may be in multiple auto-roles)

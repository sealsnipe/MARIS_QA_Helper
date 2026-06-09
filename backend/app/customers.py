from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Customer, SystemPrompt, User, UserCustomer, utc_now_iso
from app.roles_admin import assign_new_customer_to_auto_roles

CUSTOMER_SLUG_PATTERN = re.compile(r"^[a-z0-9_-]+$")

GLOBAL_CUSTOMER_ID = "global"
GLOBAL_CUSTOMER_NAME = "Global"


class CustomerAdminError(Exception):
    def __init__(self, code: str, *, status_code: int = 400, detail: str = "") -> None:
        self.code = code
        self.status_code = status_code
        self.detail = detail
        super().__init__(code)


def validate_customer_slug(customer_id: str) -> bool:
    return bool(CUSTOMER_SLUG_PATTERN.fullmatch(customer_id))


def is_customer_active(customer: Customer | None) -> bool:
    if customer is None:
        return False
    return bool(getattr(customer, "active", 1))


def collection_name(customer_id: str, prefix: str = "kb_") -> str:
    if not validate_customer_slug(customer_id):
        raise ValueError(f"invalid customer slug: {customer_id!r}")
    return f"{prefix}{customer_id}"


def is_global_customer(customer_id: str) -> bool:
    return customer_id == GLOBAL_CUSTOMER_ID


def list_customers_for_user(db: Session, user_id: str) -> list[Customer]:
    stmt = (
        select(Customer)
        .join(UserCustomer, UserCustomer.customer_id == Customer.id)
        .where(
            UserCustomer.user_id == user_id,
            Customer.id != GLOBAL_CUSTOMER_ID,
            Customer.active == 1,
        )
        .order_by(Customer.name)
    )
    return list(db.scalars(stmt))


def list_effective_tenant_customers_for_user(db: Session, user: User) -> list[Customer]:
    """Tenant customers visible in nav / chat scope: all active tenants for admins, else assignments."""
    if user.is_admin:
        return list_tenant_customers(db)
    return list_customers_for_user(db, user.id)


def list_assigned_customer_ids(db: Session, user_id: str) -> list[str]:
    user = db.get(User, user_id)
    if user is None:
        return []
    return [customer.id for customer in list_effective_tenant_customers_for_user(db, user)]


def list_customers_for_nav(db: Session, user: User) -> list[Customer]:
    """Sidebar: Global + effective tenant customers for this user."""
    assigned = list_effective_tenant_customers_for_user(db, user)
    global_customer = get_customer(db, GLOBAL_CUSTOMER_ID)

    if not assigned:
        if user.is_admin and global_customer is not None and is_customer_active(global_customer):
            return [global_customer]
        return []

    if global_customer is None or not is_customer_active(global_customer):
        return assigned

    return [global_customer, *assigned]


def list_all_customers(db: Session, *, include_global: bool = False) -> list[Customer]:
    stmt = select(Customer).where(Customer.active == 1).order_by(Customer.name)
    rows = list(db.scalars(stmt))
    if include_global:
        return rows
    return [row for row in rows if row.id != GLOBAL_CUSTOMER_ID]


def list_tenant_customers(db: Session, *, include_inactive: bool = False) -> list[Customer]:
    stmt = select(Customer).where(Customer.id != GLOBAL_CUSTOMER_ID).order_by(Customer.name)
    if not include_inactive:
        stmt = stmt.where(Customer.active == 1)
    return list(db.scalars(stmt))


def list_production_customers(db: Session) -> list[Customer]:
    """Active tenant customers (for admin dropdowns and prompts)."""
    return list_tenant_customers(db)


def user_has_customer(db: Session, user_id: str, customer_id: str) -> bool:
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        return False

    if is_global_customer(customer_id):
        global_customer = get_customer(db, GLOBAL_CUSTOMER_ID)
        if global_customer is None or not is_customer_active(global_customer):
            return False
        if user.is_admin:
            return True
        return bool(list_effective_tenant_customers_for_user(db, user))

    if not validate_customer_slug(customer_id):
        return False
    customer = get_customer(db, customer_id)
    if not is_customer_active(customer):
        return False

    if user.is_admin:
        return True

    stmt = select(UserCustomer).where(
        UserCustomer.user_id == user_id,
        UserCustomer.customer_id == customer_id,
    )
    return db.scalar(stmt) is not None


def create_tenant_customer(db: Session, customer_id: str, name: str) -> Customer:
    slug = customer_id.strip().lower()
    display_name = name.strip()
    if is_global_customer(slug):
        raise CustomerAdminError("forbidden_customer", status_code=403)
    if not validate_customer_slug(slug):
        raise CustomerAdminError("invalid_customer_id")
    if not display_name:
        raise CustomerAdminError("invalid_name")
    if db.get(Customer, slug) is not None:
        raise CustomerAdminError("customer_exists", status_code=409)

    row = Customer(id=slug, name=display_name, active=1, created_at=utc_now_iso())
    db.add(row)
    db.flush()
    admin_users = db.scalars(select(User).where(User.is_admin == 1, User.is_active == 1))
    for admin in admin_users:
        link = db.get(UserCustomer, {"user_id": admin.id, "customer_id": slug})
        if link is None:
            db.add(UserCustomer(user_id=admin.id, customer_id=slug))

    assign_new_customer_to_auto_roles(db, slug)
    db.commit()
    db.refresh(row)
    return row


def update_tenant_customer(db: Session, customer_id: str, name: str) -> Customer:
    if is_global_customer(customer_id):
        raise CustomerAdminError("forbidden_customer", status_code=403)
    row = db.get(Customer, customer_id)
    if row is None or not is_customer_active(row):
        raise CustomerAdminError("not_found", status_code=404)
    display_name = name.strip()
    if not display_name:
        raise CustomerAdminError("invalid_name")
    row.name = display_name
    db.commit()
    db.refresh(row)
    return row


def rename_tenant_customer(
    db: Session,
    old_customer_id: str,
    new_customer_id: str,
    *,
    vector_store: VectorStore | None = None,
) -> Customer:
    """Rename a tenant customer (Kürzel/slug).

    This is the central, stable place that rewires KB, Qdrant, uploads, chats, prompts, etc.
    - old row in customers is removed, new PK row created
    - all dependent rows (documents, chunks, user_customers, chat_sessions, system_prompts) updated to new slug
    - per-customer system prompt scope (if any) is moved
    - Qdrant: points copied to kb_{new} (payload customer_id updated), old collection removed
    - FS uploads: data/uploads/{old}/ -> {new}/ (best effort; warn on failure)
    """
    old_slug = old_customer_id.strip().lower()
    new_slug = new_customer_id.strip().lower()

    if is_global_customer(old_slug) or is_global_customer(new_slug):
        raise CustomerAdminError("forbidden_customer", status_code=403)
    if not validate_customer_slug(new_slug):
        raise CustomerAdminError("invalid_customer_id")
    if old_slug == new_slug:
        row = db.get(Customer, old_slug)
        if row is None or not is_customer_active(row):
            raise CustomerAdminError("not_found", status_code=404)
        return row
    if db.get(Customer, new_slug) is not None:
        raise CustomerAdminError("customer_exists", status_code=409)

    old_row = db.get(Customer, old_slug)
    if old_row is None or not is_customer_active(old_row):
        raise CustomerAdminError("not_found", status_code=404)

    from app.qdrant_store import VectorStore, get_vector_store

    store: VectorStore = vector_store or get_vector_store()

    # Stage 1: copy vector data to new collection (keep old until after sqlite success)
    try:
        store.copy_collection(old_slug, new_slug)
    except Exception as exc:
        raise CustomerAdminError("vector_store_failed", status_code=500, detail=f"copy failed: {exc}") from exc

    # Stage 2: SQLite identity move (new PK row, re-point children, delete old row)
    try:
        # create replacement customer row (preserve created_at, active, name)
        new_row = Customer(
            id=new_slug,
            name=old_row.name,
            active=old_row.active,
            created_at=old_row.created_at,
        )
        db.add(new_row)
        db.flush()

        # re-point all references (use raw UPDATE for multi-table + to avoid stale FK during delete)
        params = {"new": new_slug, "old": old_slug}

        db.execute(text("UPDATE user_customers SET customer_id = :new WHERE customer_id = :old"), params)
        db.execute(text("UPDATE documents SET customer_id = :new WHERE customer_id = :old"), params)
        db.execute(text("UPDATE chunks SET customer_id = :new WHERE customer_id = :old"), params)
        db.execute(text("UPDATE chat_sessions SET customer_id = :new WHERE customer_id = :old"), params)

        # system_prompts: move PK scope if it matches the slug (per-cust prompt), plus any FK
        prompt_row = db.get(SystemPrompt, old_slug)
        if prompt_row is not None:
            new_prompt = SystemPrompt(
                scope=new_slug,
                customer_id=new_slug,
                content=prompt_row.content,
                updated_at=prompt_row.updated_at,
                updated_by=prompt_row.updated_by,
            )
            db.add(new_prompt)
            db.delete(prompt_row)
        # catch any other prompt rows that might reference via customer_id column
        db.execute(
            text("UPDATE system_prompts SET customer_id = :new WHERE customer_id = :old"),
            params,
        )

        # now remove the old identity
        db.delete(old_row)

        db.commit()
    except Exception as exc:
        db.rollback()
        # best-effort: remove the partially created target collection to allow retry
        try:
            store.delete_collection(new_slug)
        except Exception:
            pass
        raise CustomerAdminError("rename_failed", status_code=500, detail=str(exc)) from exc

    # Stage 3: now that sqlite is on new slug, remove old qdrant collection
    try:
        store.delete_collection(old_slug)
    except Exception:
        # non-fatal; orphan collection can be cleaned manually in qdrant ui
        pass

    # Stage 4: move upload directory (best effort)
    try:
        from app.upload import _upload_root

        root = _upload_root()
        old_dir = root / old_slug
        new_dir = root / new_slug
        if old_dir.exists() and old_dir.is_dir():
            if new_dir.exists():
                # target exists (shouldn't for fresh rename) — leave as-is, admin can merge if needed
                pass
            else:
                new_dir.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(old_dir), str(new_dir))
    except Exception as fs_exc:
        # non-fatal for KB consistency; uploads are secondary
        # caller / UI can surface a warning
        logging.getLogger(__name__).warning(
            "customer rename: failed to move uploads %s -> %s : %s",
            old_slug,
            new_slug,
            fs_exc,
        )

    # return fresh row
    row = db.get(Customer, new_slug)
    if row is None:
        # should not happen
        raise CustomerAdminError("not_found", status_code=404)
    return row


def deactivate_tenant_customer(db: Session, customer_id: str) -> None:
    if is_global_customer(customer_id):
        raise CustomerAdminError("forbidden_customer", status_code=403)
    row = db.get(Customer, customer_id)
    if row is None or not is_customer_active(row):
        raise CustomerAdminError("not_found", status_code=404)
    row.active = 0
    db.commit()


def customer_to_dict(customer: Customer) -> dict:
    return {
        "id": customer.id,
        "name": customer.name,
        "active": bool(customer.active),
        "created_at": customer.created_at,
    }


def ensure_global_customer(db: Session) -> Customer:
    row = db.get(Customer, GLOBAL_CUSTOMER_ID)
    if row is None:
        row = Customer(
            id=GLOBAL_CUSTOMER_ID,
            name=GLOBAL_CUSTOMER_NAME,
            active=1,
            created_at=utc_now_iso(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    else:
        changed = False
        if row.name != GLOBAL_CUSTOMER_NAME:
            row.name = GLOBAL_CUSTOMER_NAME
            changed = True
        if not row.active:
            row.active = 1
            changed = True
        if changed:
            db.commit()
            db.refresh(row)
    return row


def get_customer(db: Session, customer_id: str) -> Customer | None:
    if not validate_customer_slug(customer_id):
        return None
    return db.get(Customer, customer_id)

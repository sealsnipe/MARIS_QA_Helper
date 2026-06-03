import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Customer, User, UserCustomer, utc_now_iso

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


def list_assigned_customer_ids(db: Session, user_id: str) -> list[str]:
    return [customer.id for customer in list_customers_for_user(db, user_id)]


def list_customers_for_nav(db: Session, user_id: str) -> list[Customer]:
    assigned = list_customers_for_user(db, user_id)
    if not assigned:
        return []

    global_customer = get_customer(db, GLOBAL_CUSTOMER_ID)
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
    if is_global_customer(customer_id):
        return bool(list_customers_for_user(db, user_id))
    if not validate_customer_slug(customer_id):
        return False
    customer = db.get(Customer, customer_id)
    if not is_customer_active(customer):
        return False
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

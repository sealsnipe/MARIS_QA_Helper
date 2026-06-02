import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Customer, UserCustomer

CUSTOMER_SLUG_PATTERN = re.compile(r"^[a-z0-9_-]+$")

GLOBAL_CUSTOMER_ID = "global"
GLOBAL_CUSTOMER_NAME = "Global"

DEMO_CUSTOMER_IDS = frozenset({"acme", "globex"})

PRODUCTION_CUSTOMER_IDS = frozenset(
    {
        "bg-ludwigshafen",
        "bg-frankfurt",
        "detmold-lippe",
        "kkrr",
    }
)


def validate_customer_slug(customer_id: str) -> bool:
    return bool(CUSTOMER_SLUG_PATTERN.fullmatch(customer_id))


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
        .where(UserCustomer.user_id == user_id, Customer.id != GLOBAL_CUSTOMER_ID)
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
    if global_customer is None:
        return assigned

    return [global_customer, *assigned]


def list_all_customers(db: Session, *, include_global: bool = False) -> list[Customer]:
    stmt = select(Customer).order_by(Customer.name)
    rows = list(db.scalars(stmt))
    if include_global:
        return rows
    return [row for row in rows if row.id != GLOBAL_CUSTOMER_ID]


def list_production_customers(db: Session) -> list[Customer]:
    stmt = (
        select(Customer)
        .where(Customer.id.in_(PRODUCTION_CUSTOMER_IDS))
        .order_by(Customer.name)
    )
    return list(db.scalars(stmt))


def user_has_customer(db: Session, user_id: str, customer_id: str) -> bool:
    if is_global_customer(customer_id):
        return bool(list_customers_for_user(db, user_id))
    if not validate_customer_slug(customer_id):
        return False
    stmt = select(UserCustomer).where(
        UserCustomer.user_id == user_id,
        UserCustomer.customer_id == customer_id,
    )
    return db.scalar(stmt) is not None


def ensure_global_customer(db: Session) -> Customer:
    row = db.get(Customer, GLOBAL_CUSTOMER_ID)
    if row is None:
        from app.models import utc_now_iso

        row = Customer(
            id=GLOBAL_CUSTOMER_ID,
            name=GLOBAL_CUSTOMER_NAME,
            created_at=utc_now_iso(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    elif row.name != GLOBAL_CUSTOMER_NAME:
        row.name = GLOBAL_CUSTOMER_NAME
        db.commit()
        db.refresh(row)
    return row


def get_customer(db: Session, customer_id: str) -> Customer | None:
    if not validate_customer_slug(customer_id):
        return None
    return db.get(Customer, customer_id)

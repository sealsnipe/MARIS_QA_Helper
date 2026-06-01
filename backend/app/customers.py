import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Customer, UserCustomer

CUSTOMER_SLUG_PATTERN = re.compile(r"^[a-z0-9_-]+$")


def validate_customer_slug(customer_id: str) -> bool:
    return bool(CUSTOMER_SLUG_PATTERN.fullmatch(customer_id))


def collection_name(customer_id: str, prefix: str = "kb_") -> str:
    if not validate_customer_slug(customer_id):
        raise ValueError(f"invalid customer slug: {customer_id!r}")
    return f"{prefix}{customer_id}"


def list_customers_for_user(db: Session, user_id: str) -> list[Customer]:
    stmt = (
        select(Customer)
        .join(UserCustomer, UserCustomer.customer_id == Customer.id)
        .where(UserCustomer.user_id == user_id)
        .order_by(Customer.name)
    )
    return list(db.scalars(stmt))


def user_has_customer(db: Session, user_id: str, customer_id: str) -> bool:
    if not validate_customer_slug(customer_id):
        return False
    stmt = select(UserCustomer).where(
        UserCustomer.user_id == user_id,
        UserCustomer.customer_id == customer_id,
    )
    return db.scalar(stmt) is not None


def get_customer(db: Session, customer_id: str) -> Customer | None:
    if not validate_customer_slug(customer_id):
        return None
    return db.get(Customer, customer_id)

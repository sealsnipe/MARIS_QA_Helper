from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.auth import NotAuthenticatedError, get_current_user
from app.customers import get_customer, user_has_customer
from app.db import get_db
from app.models import Customer, User


class ForbiddenCustomerError(Exception):
    pass


class CustomerNotFoundError(Exception):
    pass


async def get_current_customer(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Customer:
    customer_id = request.session.get("customer_id")
    if not customer_id:
        raise ForbiddenCustomerError()

    if not user_has_customer(db, user.id, customer_id):
        raise ForbiddenCustomerError()

    customer = get_customer(db, customer_id)
    if customer is None:
        raise ForbiddenCustomerError()

    return customer

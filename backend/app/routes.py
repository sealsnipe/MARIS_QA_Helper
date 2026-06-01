from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import NotAuthenticatedError, get_current_user, get_user_by_email, verify_password
from app.customers import get_customer, list_customers_for_user, user_has_customer
from app.db import get_db
from app.models import User
from app.tenant import (
    CustomerNotFoundError,
    ForbiddenCustomerError,
    get_current_customer,
)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


class CustomerSwitchRequest(BaseModel):
    customer_id: str = Field(min_length=1)


@router.get("/api/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request, error: str | None = None) -> HTMLResponse:
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": error},
    )


@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    user = get_user_by_email(db, email)
    if user is None or not verify_password(user.password_hash, password):
        return RedirectResponse(
            url="/login?error=1",
            status_code=status.HTTP_302_FOUND,
        )

    request.session.clear()
    request.session["user_id"] = user.id

    customers = list_customers_for_user(db, user.id)
    if len(customers) == 1:
        request.session["customer_id"] = customers[0].id

    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)


@router.post("/logout")
def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)


@router.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    customers = list_customers_for_user(db, user.id)
    active_customer_id = request.session.get("customer_id")
    active_customer = get_customer(db, active_customer_id) if active_customer_id else None
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "user": user,
            "customers": customers,
            "active_customer": active_customer,
        },
    )


@router.get("/api/customers")
def api_list_customers(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    customers = list_customers_for_user(db, user.id)
    return {
        "customers": [{"id": customer.id, "name": customer.name} for customer in customers],
        "active": request.session.get("customer_id"),
    }


@router.post("/api/session/customer")
def api_set_customer(
    payload: CustomerSwitchRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    customer_id = payload.customer_id.strip()
    customer = get_customer(db, customer_id)
    if customer is None:
        raise CustomerNotFoundError()

    if not user_has_customer(db, user.id, customer_id):
        raise ForbiddenCustomerError()

    request.session["customer_id"] = customer_id
    return JSONResponse({"active": customer_id})


@router.get("/api/me")
def api_me(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Protected JSON route for auth smoke tests."""
    return {
        "user_id": user.id,
        "email": user.email,
        "active_customer": request.session.get("customer_id"),
    }


@router.get("/api/tenant-check")
def api_tenant_check(
    customer=Depends(get_current_customer),
) -> dict:
    """Protected tenant-scoped JSON route for M2 tests."""
    return {"customer_id": customer.id, "customer_name": customer.name}

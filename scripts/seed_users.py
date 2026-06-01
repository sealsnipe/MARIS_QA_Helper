#!/usr/bin/env python3
"""Seed users and user↔customer assignments (idempotent)."""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.auth import hash_password
from app.customers import validate_customer_slug
from app.db import SessionLocal, init_db
from app.models import Customer, User, UserCustomer, utc_now_iso

DEFAULT_USERS = (
    {
        "email": "sven@example.com",
        "password": "GeheimesPW!",
        "customers": ("acme", "globex"),
    },
    {
        "email": "anna@example.com",
        "password": "GeheimesPW!",
        "customers": ("globex",),
    },
)


def _ensure_user(db, email: str, password: str) -> User:
    normalized = email.strip().lower()
    user = db.scalar(select(User).where(User.email == normalized))
    if user is None:
        user = User(
            id=str(uuid.uuid4()),
            email=normalized,
            password_hash=hash_password(password),
            is_active=1,
            created_at=utc_now_iso(),
        )
        db.add(user)
        db.flush()
        print(f"Created user {normalized}")
    else:
        print(f"User exists {normalized}")
    return user


def _ensure_membership(db, user: User, customer_ids: tuple[str, ...]) -> None:
    for customer_id in customer_ids:
        if not validate_customer_slug(customer_id):
            raise ValueError(f"invalid customer slug: {customer_id!r}")
        if db.get(Customer, customer_id) is None:
            raise ValueError(f"unknown customer: {customer_id!r}")

        link = db.get(UserCustomer, {"user_id": user.id, "customer_id": customer_id})
        if link is None:
            db.add(UserCustomer(user_id=user.id, customer_id=customer_id))
            print(f"Linked {user.email} -> {customer_id}")


def seed_user(email: str, password: str, customers: tuple[str, ...]) -> None:
    init_db()
    with SessionLocal() as db:
        user = _ensure_user(db, email, password)
        _ensure_membership(db, user, customers)
        db.commit()


def seed_defaults() -> None:
    for entry in DEFAULT_USERS:
        seed_user(entry["email"], entry["password"], entry["customers"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed users for SUP_QA_Helper")
    parser.add_argument("--email", help="User email")
    parser.add_argument("--password", help="User password")
    parser.add_argument(
        "--customers",
        help="Comma-separated customer slugs (e.g. acme,globex)",
    )
    parser.add_argument(
        "--defaults",
        action="store_true",
        help="Seed demo users sven@example.com and anna@example.com",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.defaults or (not args.email and not args.password and not args.customers):
        seed_defaults()
        return

    if not args.email or not args.password or not args.customers:
        raise SystemExit("Provide --email, --password and --customers, or use --defaults")

    customer_ids = tuple(part.strip() for part in args.customers.split(",") if part.strip())
    seed_user(args.email, args.password, customer_ids)


if __name__ == "__main__":
    main()

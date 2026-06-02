#!/usr/bin/env python3
"""Seed users and user↔customer assignments (idempotent)."""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from sqlalchemy import select

from app.auth import hash_password
from app.customers import validate_customer_slug
from app.db import SessionLocal, init_db
from app.models import Customer, User, UserCustomer, utc_now_iso
from seed_data import ADMIN_EMAILS, DEFAULT_USERS


def _ensure_user(db, email: str, password: str, *, is_admin: bool = False) -> User:
    normalized = email.strip().lower()
    user = db.scalar(select(User).where(User.email == normalized))
    if user is None:
        user = User(
            id=str(uuid.uuid4()),
            email=normalized,
            password_hash=hash_password(password),
            is_active=1,
            is_admin=1 if is_admin else 0,
            created_at=utc_now_iso(),
        )
        db.add(user)
        db.flush()
        print(f"Created user {normalized}" + (" (admin)" if is_admin else ""))
    else:
        if is_admin and not user.is_admin:
            user.is_admin = 1
            print(f"Promoted to admin {normalized}")
        else:
            print(f"User exists {normalized}")
    return user


def _ensure_membership(db, user: User, customer_ids: tuple[str, ...]) -> None:
    for customer_id in customer_ids:
        if not validate_customer_slug(customer_id):
            raise ValueError(f"invalid customer slug: {customer_id!r}")
        if db.get(Customer, customer_id) is None:
            raise ValueError(f"unknown customer: {customer_id!r} — run seed_customers.py first")

        link = db.get(UserCustomer, {"user_id": user.id, "customer_id": customer_id})
        if link is None:
            db.add(UserCustomer(user_id=user.id, customer_id=customer_id))
            print(f"Linked {user.email} -> {customer_id}")


def seed_user(email: str, password: str, customers: tuple[str, ...], *, is_admin: bool = False) -> None:
    init_db()
    with SessionLocal() as db:
        user = _ensure_user(db, email, password, is_admin=is_admin)
        _ensure_membership(db, user, customers)
        db.commit()


def seed_defaults() -> None:
    for entry in DEFAULT_USERS:
        seed_user(
            entry["email"],
            entry["password"],
            entry["customers"],
            is_admin=entry.get("is_admin", False),
        )
    with SessionLocal() as db:
        for email in ADMIN_EMAILS:
            user = db.scalar(select(User).where(User.email == email))
            if user and not user.is_admin:
                user.is_admin = 1
        db.commit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed users for SUP_QA_Helper")
    parser.add_argument("--email", help="User email")
    parser.add_argument("--password", help="User password")
    parser.add_argument(
        "--customers",
        help="Comma-separated customer slugs (e.g. bg-ludwigshafen,kkrr)",
    )
    parser.add_argument(
        "--defaults",
        action="store_true",
        help="Seed default users (admin + demo users for tests)",
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

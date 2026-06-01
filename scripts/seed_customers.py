#!/usr/bin/env python3
"""Seed demo customers (idempotent)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.models import Customer, utc_now_iso

DEFAULT_CUSTOMERS = (
    ("acme", "Acme GmbH"),
    ("globex", "Globex AG"),
)


def seed_customers(customers: tuple[tuple[str, str], ...] = DEFAULT_CUSTOMERS) -> None:
    init_db()
    with SessionLocal() as db:
        for customer_id, name in customers:
            existing = db.get(Customer, customer_id)
            if existing is None:
                db.add(
                    Customer(
                        id=customer_id,
                        name=name,
                        created_at=utc_now_iso(),
                    )
                )
        db.commit()

        rows = list(db.scalars(select(Customer).order_by(Customer.id)))
        print(f"Customers ready ({len(rows)}): {', '.join(c.id for c in rows)}")


if __name__ == "__main__":
    seed_customers()

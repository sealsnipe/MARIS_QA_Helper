#!/usr/bin/env python3
"""Seed customers (production + demo, idempotent)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.models import Customer, utc_now_iso
from seed_data import ALL_CUSTOMERS


def seed_customers(customers: tuple[tuple[str, str], ...] = ALL_CUSTOMERS) -> None:
    init_db()
    with SessionLocal() as db:
        for customer_id, name in customers:
            existing = db.get(Customer, customer_id)
            if existing is None:
                db.add(
                    Customer(
                        id=customer_id,
                        name=name,
                        active=1,
                        created_at=utc_now_iso(),
                    )
                )
                print(f"Created customer {customer_id} ({name})")
            elif existing.name != name:
                existing.name = name
                print(f"Updated customer name {customer_id} -> {name}")
        db.commit()

        rows = list(db.scalars(select(Customer).order_by(Customer.name)))
        print(f"Customers ready ({len(rows)}):")
        for row in rows:
            print(f"  - {row.id}: {row.name}")


if __name__ == "__main__":
    seed_customers()

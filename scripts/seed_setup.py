#!/usr/bin/env python3
"""Seed customers + admin user during setup (dev or prod profile)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from seed_customers import seed_customers
from seed_data import GLOBAL_CUSTOMER, PRODUCTION_CUSTOMERS
from seed_users import seed_user

DEFAULT_ADMIN_EMAIL = "matthias.schindler@maris-healthcare.de"
DeployProfile = Literal["dev", "prod"]


def run_seed(*, profile: DeployProfile, email: str, password: str) -> None:
    _ = profile  # dev and prod use the same customer set
    normalized = email.strip().lower()
    customers = (GLOBAL_CUSTOMER,) + PRODUCTION_CUSTOMERS
    customer_ids = tuple(slug for slug, _ in PRODUCTION_CUSTOMERS)

    seed_customers(customers)
    seed_user(normalized, password, customer_ids, is_admin=True)
    print(f"Admin-Nutzer bereit: {normalized}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed customers and admin user (setup / manual)")
    parser.add_argument("--profile", choices=("dev", "prod"), default="dev")
    parser.add_argument("--email", default=os.environ.get("SEED_ADMIN_EMAIL", DEFAULT_ADMIN_EMAIL))
    parser.add_argument(
        "--password",
        default=os.environ.get("SEED_ADMIN_PASSWORD", ""),
        help="Prefer SEED_ADMIN_PASSWORD env (not in shell history)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    password = (args.password or "").strip()
    if not password:
        raise SystemExit("Passwort fehlt — SEED_ADMIN_PASSWORD oder --password setzen.")
    run_seed(profile=args.profile, email=args.email, password=password)


if __name__ == "__main__":
    main()

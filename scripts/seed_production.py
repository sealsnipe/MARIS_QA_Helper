#!/usr/bin/env python3
"""Production seed: customers + admin user (password via prompt/env, never in repo)."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from seed_setup import DEFAULT_ADMIN_EMAIL, run_seed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed production customers and admin user")
    parser.add_argument("--email", default=DEFAULT_ADMIN_EMAIL, help="Admin login email")
    parser.add_argument(
        "--password",
        help="Admin password (prefer SEED_ADMIN_PASSWORD env or interactive prompt)",
    )
    return parser.parse_args()


def _resolve_password(cli_password: str | None) -> str:
    if cli_password:
        return cli_password
    env_password = os.environ.get("SEED_ADMIN_PASSWORD", "").strip()
    if env_password:
        return env_password
    entered = getpass.getpass("Admin-Passwort (versteckt): ").strip()
    if not entered:
        raise SystemExit("Passwort fehlt. Setze SEED_ADMIN_PASSWORD oder --password.")
    confirm = getpass.getpass("Passwort wiederholen: ").strip()
    if entered != confirm:
        raise SystemExit("Passwörter stimmen nicht überein.")
    return entered


def main() -> None:
    args = parse_args()
    password = _resolve_password(args.password)
    run_seed(profile="prod", email=args.email.strip().lower(), password=password)
    print(f"Production seed done for {args.email}")


if __name__ == "__main__":
    main()

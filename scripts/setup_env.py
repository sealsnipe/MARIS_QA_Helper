#!/usr/bin/env python3
"""Create or update local .env with secrets (never committed)."""

from __future__ import annotations

import argparse
import getpass
import re
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
EXAMPLE_PATH = ROOT / ".env.example"

PLACEHOLDER_KEY = "sk-placeholder-replace-me"
KEY_PATTERN = re.compile(r"^sk-[A-Za-z0-9_-]{10,}$")


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        raise SystemExit(f"Missing {path}")
    return path.read_text(encoding="utf-8").splitlines()


def _write_env(lines: list[str]) -> None:
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Updated {ENV_PATH}")


def _upsert(lines: list[str], key: str, value: str) -> list[str]:
    prefix = f"{key}="
    replaced = False
    updated: list[str] = []
    for line in lines:
        if line.startswith(prefix):
            updated.append(f"{prefix}{value}")
            replaced = True
        else:
            updated.append(line)
    if not replaced:
        updated.append(f"{prefix}{value}")
    return updated


def _validate_openai_key(value: str) -> str:
    cleaned = value.strip()
    if cleaned in {PLACEHOLDER_KEY, "sk-...", "sk-your-key-here"}:
        raise SystemExit("Refusing placeholder OpenAI key.")
    if not KEY_PATTERN.fullmatch(cleaned):
        raise SystemExit("OpenAI key must look like sk-... (no spaces).")
    return cleaned


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Set up local .env secrets for SUP_QA_Helper")
    parser.add_argument(
        "--openai-key",
        help="OpenAI API key (sk-...). Prefer --from-env or interactive prompt to avoid shell history.",
    )
    parser.add_argument(
        "--from-env",
        action="store_true",
        help="Read OPENAI_API_KEY from current environment variable",
    )
    parser.add_argument(
        "--regenerate-session-secret",
        action="store_true",
        help="Generate a fresh SESSION_SECRET even if one already exists",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Validate .env without writing changes",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    lines = _read_lines(ENV_PATH if ENV_PATH.exists() else EXAMPLE_PATH)

    current_key = next(
        (line.split("=", 1)[1] for line in lines if line.startswith("OPENAI_API_KEY=")),
        "",
    )
    current_secret = next(
        (line.split("=", 1)[1] for line in lines if line.startswith("SESSION_SECRET=")),
        "",
    )

    openai_key: str | None = None
    if args.from_env:
        import os

        candidate = os.environ.get("OPENAI_API_KEY", "").strip()
        if candidate:
            openai_key = _validate_openai_key(candidate)
    elif args.openai_key:
        openai_key = _validate_openai_key(args.openai_key)
    elif current_key in {"", PLACEHOLDER_KEY} and not args.check_only:
        entered = getpass.getpass("OpenAI API key (sk-..., hidden): ").strip()
        if entered:
            openai_key = _validate_openai_key(entered)

    if args.check_only:
        key_ok = bool(current_key) and current_key != PLACEHOLDER_KEY and KEY_PATTERN.fullmatch(current_key)
        secret_ok = bool(current_secret) and "change-me" not in current_secret and len(current_secret) >= 32
        print(f"OPENAI_API_KEY: {'OK' if key_ok else 'MISSING_OR_PLACEHOLDER'}")
        print(f"SESSION_SECRET: {'OK' if secret_ok else 'WEAK_OR_PLACEHOLDER'}")
        if not key_ok or not secret_ok:
            raise SystemExit(1)
        print("Env looks ready for smoke tests.")
        return

    changed = False
    if openai_key:
        lines = _upsert(lines, "OPENAI_API_KEY", openai_key)
        changed = True
        print("OPENAI_API_KEY set.")

    needs_secret = (
        args.regenerate_session_secret
        or not current_secret
        or "change-me" in current_secret
        or len(current_secret) < 32
    )
    if needs_secret:
        lines = _upsert(lines, "SESSION_SECRET", secrets.token_urlsafe(48))
        changed = True
        print("SESSION_SECRET generated.")

    if not changed:
        print("No changes needed. Use --check-only to validate.")
        return

    _write_env(lines)
    print("Next: python scripts/smoke_openai.py")


if __name__ == "__main__":
    main()

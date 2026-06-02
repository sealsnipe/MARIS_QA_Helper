#!/usr/bin/env python3
"""Import ChatGPT OAuth tokens from Codex CLI auth.json into oauth-codex format."""

from __future__ import annotations

import argparse
import base64
import json
import os
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "auth.json"
DEFAULT_TARGET = Path.home() / ".oauth_codex" / "auth.json"
WINDOWS_FALLBACK = Path("/mnt/c/Users/Matthias/.codex/auth.json")


def _resolve_source(path: Path | None) -> Path:
    if path is not None:
        return path.expanduser()
    if DEFAULT_SOURCE.exists():
        return DEFAULT_SOURCE
    if WINDOWS_FALLBACK.exists():
        return WINDOWS_FALLBACK
    return DEFAULT_SOURCE


def _load_codex_auth(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Invalid auth file: {path}")
    return payload


def _jwt_expires_at(access_token: str) -> float | None:
    try:
        parts = access_token.split(".")
        if len(parts) < 2:
            return None
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        exp = claims.get("exp")
        return float(exp) if exp is not None else None
    except (ValueError, json.JSONDecodeError, TypeError):
        return None


def _to_oauth_codex_payload(codex_auth: dict) -> dict:
    tokens = codex_auth.get("tokens")
    if isinstance(tokens, dict) and tokens.get("access_token"):
        source = tokens
    elif codex_auth.get("access_token"):
        source = codex_auth
    else:
        raise SystemExit("No OAuth access_token found in Codex auth file.")

    access_token = source["access_token"]
    return {
        "access_token": access_token,
        "refresh_token": source.get("refresh_token"),
        "id_token": source.get("id_token"),
        "token_type": source.get("token_type", "Bearer"),
        "account_id": source.get("account_id"),
        "api_key": codex_auth.get("OPENAI_API_KEY"),
        "last_refresh": codex_auth.get("last_refresh"),
        "expires_at": _jwt_expires_at(access_token),
    }


def import_auth(source: Path, target: Path, *, force: bool) -> None:
    if not source.exists():
        raise SystemExit(
            f"Codex auth not found at {source}.\n"
            "Run first:  npx @openai/codex login   (or codex login on Windows)"
        )
    if target.exists() and not force:
        raise SystemExit(f"Target already exists: {target}\nUse --force to overwrite.")

    payload = _to_oauth_codex_payload(_load_codex_auth(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    target.chmod(stat.S_IRUSR | stat.S_IWUSR)

    account = payload.get("account_id") or "unknown"
    print(f"Imported OAuth tokens from {source}")
    print(f"Saved oauth-codex auth to {target}")
    print(f"ChatGPT account_id: {account}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import Codex OAuth auth for chat smoke tests")
    parser.add_argument("--source", type=Path, help=f"Codex auth.json (default: {DEFAULT_SOURCE})")
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET, help="oauth-codex auth target")
    parser.add_argument("--force", action="store_true", help="Overwrite existing target auth file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    import_auth(_resolve_source(args.source), args.target.expanduser(), force=args.force)


if __name__ == "__main__":
    main()

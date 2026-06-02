#!/usr/bin/env python3
"""Manual smoke: Chat via ChatGPT OAuth (Codex backend). Embeddings use API key separately."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings

DEFAULT_OAUTH_AUTH = Path.home() / ".oauth_codex" / "auth.json"
# Platform API models (gpt-4.1-mini etc.) do NOT work on the Codex/ChatGPT OAuth backend.
CODEX_MODELS = ("gpt-5.4-mini", "gpt-5.3-codex-spark", "gpt-5.3-codex", "gpt-5.2", "gpt-5.4")
DEFAULT_INSTRUCTIONS = "Du bist ein Support-Assistent. Antworte knapp auf Deutsch."


def _ensure_oauth_auth(path: Path) -> None:
    if path.exists():
        return
    raise SystemExit(
        f"OAuth auth missing at {path}.\n"
        "Run first:  python3 scripts/login_chat_oauth.py"
    )


def _auth_headers(auth_path: Path) -> dict[str, str]:
    try:
        from oauth_codex import Client
        from oauth_codex.store import FileTokenStore
    except ImportError as exc:
        raise SystemExit("Missing dependency oauth-codex. Install: pip install oauth-codex") from exc

    settings = get_settings()
    client = Client(
        token_store=FileTokenStore(path=auth_path),
        base_url=settings.CODEX_BASE_URL,
    )
    client.authenticate()
    headers = dict(client.auth.get_headers())
    headers["Content-Type"] = "application/json"
    headers["Accept"] = "text/event-stream"
    return headers


def _run_chat(model: str, auth_path: Path) -> tuple[str, str]:
    settings = get_settings()
    headers = _auth_headers(auth_path)
    payload = {
        "model": model,
        "input": [{"role": "user", "content": "Antworte exakt mit einem Wort: OK"}],
        "instructions": DEFAULT_INSTRUCTIONS,
        "store": False,
        "stream": True,
    }

    with httpx.stream(
        "POST",
        f"{settings.CODEX_BASE_URL.rstrip('/')}/responses",
        headers=headers,
        json=payload,
        timeout=120.0,
    ) as response:
        if response.status_code >= 400:
            body = response.read().decode(errors="replace")
            raise RuntimeError(f"{response.status_code} {body[:300]}")

        parts: list[str] = []
        for line in response.iter_lines():
            if not line.startswith("data: ") or line == "data: [DONE]":
                continue
            event = json.loads(line[6:])
            if event.get("type") == "response.output_text.delta":
                parts.append(event.get("delta") or "")

    answer = "".join(parts).strip()
    if not answer:
        raise RuntimeError("empty answer from Codex stream")
    return model, answer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test ChatGPT OAuth chat backend")
    parser.add_argument("--model", help="Codex model id (default: CHAT_MODEL from .env)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    get_settings.cache_clear()
    settings = get_settings()
    auth_path = DEFAULT_OAUTH_AUTH
    _ensure_oauth_auth(auth_path)

    if settings.LLM_AUTH_MODE != "chatgpt_oauth":
        print(f"Note: LLM_AUTH_MODE={settings.LLM_AUTH_MODE!r} (expected 'chatgpt_oauth' for this smoke).")

    preferred = args.model or settings.CHAT_MODEL
    models = [preferred, *[m for m in CODEX_MODELS if m != preferred]]
    last_error: Exception | None = None

    print(f"Codex backend: {settings.CODEX_BASE_URL}")
    print(f"Embeddings still use OPENAI_API_KEY via {settings.OPENAI_BASE_URL}")
    print(f"OAuth auth: {auth_path}")

    for model in models:
        print(f"\nChat OAuth try model={model} ...", end=" ", flush=True)
        try:
            used_model, answer = _run_chat(model, auth_path)
        except Exception as exc:
            last_error = exc
            message = str(exc).lower()
            if "expired" in message or "refresh_token" in message or "401" in message:
                print(f"FAILED ({exc})")
                print("\nOAuth session stale. Re-login:\n  python3 scripts/login_chat_oauth.py")
                raise SystemExit(1) from exc
            print(f"FAILED ({exc})")
            continue
        print(f"OK (answer={answer!r})")
        print(f"\nChat OAuth brain check passed with model={used_model}.")
        if model != preferred and preferred not in CODEX_MODELS:
            print(f"Hint: set CHAT_MODEL={used_model} in .env for OAuth chat.")
        return

    raise SystemExit(f"All chat model attempts failed. Last error: {last_error}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Manual smoke test: verify OpenAI chat + embedding using .env (requires network)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from openai import OpenAI

from app.config import get_settings

FALLBACK_CHAT_MODEL = "gpt-4o-mini"
PLACEHOLDER_KEY = "sk-placeholder-replace-me"


def _ensure_real_key(api_key: str) -> None:
    if not api_key or api_key == PLACEHOLDER_KEY or api_key.startswith("sk-placeholder"):
        raise SystemExit(
            "OPENAI_API_KEY is still a placeholder.\n"
            "Run:  python scripts/setup_env.py\n"
            "Or:   OPENAI_API_KEY=sk-... python scripts/setup_env.py --from-env"
        )


def _test_embedding(client: OpenAI, model: str, dim: int) -> list[float]:
    response = client.embeddings.create(
        model=model,
        input="SUP_QA_Helper connectivity check.",
    )
    vector = response.data[0].embedding
    if len(vector) != dim:
        raise RuntimeError(f"Embedding dim mismatch: expected {dim}, got {len(vector)}")
    return vector


def _test_chat(client: OpenAI, model: str) -> tuple[str, str]:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": "Antworte exakt mit einem Wort: OK",
            }
        ],
        max_tokens=8,
    )
    text = (response.choices[0].message.content or "").strip()
    return model, text


def main() -> None:
    get_settings.cache_clear()
    settings = get_settings()
    _ensure_real_key(settings.OPENAI_API_KEY)

    client = OpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
    )

    print(f"Base URL: {settings.OPENAI_BASE_URL}")
    print(f"Embedding model: {settings.EMBEDDING_MODEL} (dim={settings.EMBEDDING_DIM})")
    print(f"Chat model: {settings.CHAT_MODEL}")

    print("\n[1/2] Embedding ...", end=" ", flush=True)
    vector = _test_embedding(client, settings.EMBEDDING_MODEL, settings.EMBEDDING_DIM)
    print(f"OK ({len(vector)} dims, first={vector[0]:.4f})")

    print("[2/2] Chat ...", end=" ", flush=True)
    used_model = settings.CHAT_MODEL
    try:
        used_model, answer = _test_chat(client, settings.CHAT_MODEL)
    except Exception as primary_error:
        print(f"FAILED ({primary_error})")
        print(f"      Retrying with fallback {FALLBACK_CHAT_MODEL} ...", end=" ", flush=True)
        used_model, answer = _test_chat(client, FALLBACK_CHAT_MODEL)
        print("OK (fallback)")
        print(
            f"\nHint: set CHAT_MODEL={FALLBACK_CHAT_MODEL} in .env if {settings.CHAT_MODEL} "
            "is unavailable on your account."
        )
    else:
        print(f"OK (model={used_model}, answer={answer!r})")

    print("\nBrain check passed: OpenAI key, embeddings, and chat are working.")


if __name__ == "__main__":
    main()

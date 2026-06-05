from __future__ import annotations

import json
import stat
import time
from pathlib import Path
from typing import Any


def save_oauth_tokens(target: Path, payload: dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    target.chmod(stat.S_IRUSR | stat.S_IWUSR)


def load_oauth_tokens(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def oauth_tokens_configured(path: Path) -> bool:
    data = load_oauth_tokens(path)
    token = (data.get("access_token") or "").strip()
    return bool(token) and path.exists() and path.stat().st_size > 10


def touch_token_refresh(path: Path, data: dict[str, Any]) -> None:
    data["last_refresh"] = time.time()
    save_oauth_tokens(path, data)

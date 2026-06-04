from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.models import AppSecret, utc_now_iso


class SecretsAdminError(Exception):
    def __init__(self, code: str, *, status_code: int = 400, detail: str = "") -> None:
        self.code = code
        self.status_code = status_code
        self.detail = detail
        super().__init__(code)


KNOWN_SECRETS = {
    "chat_api_key",
    "chat_auth_mode",
    "embedding_api_key",
    "similarity_mode",
    "similarity_api_key",
    "similarity_auth_mode",
    "integration_api_token",
}


def _is_valid_secret_name(name: str) -> bool:
    return name in KNOWN_SECRETS


def _mask_value(v: str | None) -> str:
    if not v:
        return ""
    s = str(v).strip()
    if not s:
        return ""
    if len(s) <= 4:
        return "••••"
    return "••••••••" + s[-4:]


def _get_db_secret(db: Session, name: str) -> str | None:
    row = db.get(AppSecret, name)
    if row is None:
        return None
    val = (row.value or "").strip()
    # store empty string to mean "override to empty" (e.g. disable integration)
    return val


def get_effective_secret(db: Session | None, name: str) -> str | None:
    if db is None:
        tmp = SessionLocal()
        try:
            return _get_db_or_default(tmp, name)
        finally:
            tmp.close()
    return _get_db_or_default(db, name)


def _get_db_or_default(db: Session, name: str) -> str | None:
    db_val = _get_db_secret(db, name)
    if db_val is not None:
        # explicit override (may be "" to clear)
        return db_val or None

    settings = get_settings()
    if name in ("chat_api_key", "embedding_api_key", "similarity_api_key"):
        return settings.OPENAI_API_KEY
    if name == "chat_auth_mode":
        return settings.LLM_AUTH_MODE
    if name == "similarity_auth_mode":
        # fall back to chat's mode
        return get_effective_secret(db, "chat_auth_mode") or settings.LLM_AUTH_MODE
    if name == "similarity_mode":
        return "same_as_chat"
    if name == "integration_api_token":
        tok = settings.INTEGRATION_API_TOKEN or ""
        return tok or None
    return None


def get_keys_status(db: Session) -> dict[str, Any]:
    settings = get_settings()

    chat_auth = get_effective_secret(db, "chat_auth_mode") or settings.LLM_AUTH_MODE
    chat_key = get_effective_secret(db, "chat_api_key") if chat_auth == "api_key" else None

    emb_key = get_effective_secret(db, "embedding_api_key")

    sim_mode = get_effective_secret(db, "similarity_mode") or "same_as_chat"
    sim_auth = get_effective_secret(db, "similarity_auth_mode") if sim_mode == "custom" else chat_auth
    sim_key = get_effective_secret(db, "similarity_api_key") if sim_mode == "custom" and sim_auth == "api_key" else None

    integ = get_effective_secret(db, "integration_api_token") or ""

    def _oauth_info(mode: str) -> dict[str, Any]:
        if mode != "chatgpt_oauth":
            return {"mode": "api_key"}
        try:
            p = Path(settings.codex_oauth_auth_path)
            configured = bool(p.exists() and p.stat().st_size > 10)
            info: dict[str, Any] = {"configured": configured}
            if configured:
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    if data.get("account_id"):
                        info["account_id"] = data["account_id"]
                except Exception:
                    pass
            return {"mode": "chatgpt_oauth", **info}
        except Exception:
            return {"mode": "chatgpt_oauth", "configured": False}

    return {
        "chat": {
            "auth_mode": chat_auth,
            "api_key_masked": _mask_value(chat_key) if chat_key else "",
            "oauth": _oauth_info(chat_auth),
        },
        "embedding": {
            "api_key_masked": _mask_value(emb_key),
        },
        "similarity": {
            "mode": sim_mode,
            "auth_mode": sim_auth,
            "api_key_masked": _mask_value(sim_key) if sim_key else "",
            "oauth": _oauth_info(sim_auth),
        },
        "integration": {
            "api_key_masked": _mask_value(integ) if integ else "",
            "enabled": bool(integ.strip()),
        },
    }


def update_secret(db: Session, name: str, value: str | None, updated_by: str) -> None:
    if not _is_valid_secret_name(name):
        raise SecretsAdminError("unknown_secret", status_code=400, detail=name)

    cleaned = (value or "").strip()

    if name in ("chat_auth_mode", "similarity_auth_mode"):
        if cleaned not in ("api_key", "chatgpt_oauth"):
            raise SecretsAdminError("invalid_auth_mode")
    if name == "similarity_mode":
        if cleaned not in ("same_as_chat", "custom"):
            raise SecretsAdminError("invalid_mode")
    if name in ("chat_api_key", "embedding_api_key", "similarity_api_key"):
        if cleaned and len(cleaned) < 8:
            raise SecretsAdminError("invalid_key", detail="key looks too short")

    now = utc_now_iso()
    row = db.get(AppSecret, name)
    if row is None:
        row = AppSecret(key=name, value=cleaned, updated_at=now, updated_by=updated_by)
        db.add(row)
    else:
        row.value = cleaned
        row.updated_at = now
        row.updated_by = updated_by

    db.commit()

    # bust caches so next get_* picks up the (new) override from DB
    try:
        from app.config import get_settings as _gs
        _gs.cache_clear()
    except Exception:
        pass
    try:
        from app.llm import set_llm, set_similarity_llm
        set_llm(None)
        set_similarity_llm(None)
    except Exception:
        pass
    try:
        from app.embeddings import set_embeddings_backend
        set_embeddings_backend(None)
    except Exception:
        pass

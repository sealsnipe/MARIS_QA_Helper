from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

import json
from pathlib import Path

from app.config import get_settings
from app.llm_catalog import LLM_SLOTS, get_catalog, is_valid_provider_model
from app.models import LlmPreset, LlmSlotBinding, utc_now_iso
from app.oauth_token_store import oauth_tokens_configured, save_oauth_tokens, load_oauth_tokens


class LlmPresetsError(Exception):
    def __init__(self, code: str, *, status_code: int = 400, detail: str = "") -> None:
        self.code = code
        self.status_code = status_code
        self.detail = detail
        super().__init__(code)


def oauth_dir() -> Path:
    settings = get_settings()
    base = Path(settings.MARIS_OAUTH_DIR).expanduser()
    base.mkdir(parents=True, exist_ok=True)
    return base


def preset_token_path(preset_id: str) -> Path:
    return oauth_dir() / f"{preset_id}.json"


def ensure_oauth_token_file(preset: LlmPreset) -> None:
    """If the token lives in the DB column (persisted), but the file is missing
    (e.g. after Docker rebuild or container recreation), recreate the file from DB.
    This makes OAuth survive restarts/rebuilds without requiring re-login.
    """
    token_json = getattr(preset, "oauth_token", None)
    if not token_json:
        return
    target = Path(preset.oauth_token_path)
    if target.exists() and target.stat().st_size > 10:
        return
    try:
        data = json.loads(token_json)
        save_oauth_tokens(target, data)
    except Exception:
        # will surface as auth error on next use, which is fine
        pass


def save_oauth_token(db: Session, preset_id: str, payload: dict[str, Any]) -> None:
    """Persist the OAuth token payload both to the file (for current auth code)
    and to the DB column (so it survives container rebuilds/restarts).
    """
    if not payload:
        return
    row = get_preset(db, preset_id)
    row.oauth_token = json.dumps(payload, ensure_ascii=True)
    db.commit()
    db.refresh(row)
    # keep file in sync for code that reads the Path
    target = Path(row.oauth_token_path)
    save_oauth_tokens(target, payload)


def load_oauth_token_for_preset(row: LlmPreset) -> dict[str, Any]:
    """Prefer DB-stored token (survives restarts), fall back to file."""
    token_json = getattr(row, "oauth_token", None)
    if token_json:
        try:
            return json.loads(token_json)
        except Exception:
            pass
    return load_oauth_tokens(Path(row.oauth_token_path))


def _preset_to_dict(row: LlmPreset) -> dict[str, Any]:
    path = Path(row.oauth_token_path)
    # configured if token in DB (new persistent storage) or legacy file
    configured = bool(getattr(row, "oauth_token", None)) or oauth_tokens_configured(path)
    return {
        "id": row.id,
        "name": row.name,
        "provider": row.provider,
        "model_id": row.model_id,
        "oauth_configured": configured,
        "oauth_account_label": row.oauth_account_label or "",
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def list_presets(db: Session) -> list[dict[str, Any]]:
    rows = db.scalars(select(LlmPreset).order_by(LlmPreset.name)).all()
    return [_preset_to_dict(row) for row in rows]


def get_preset(db: Session, preset_id: str) -> LlmPreset:
    row = db.get(LlmPreset, preset_id)
    if row is None:
        raise LlmPresetsError("preset_not_found", status_code=404)
    return row


def create_preset(db: Session, *, name: str, provider: str, model_id: str, updated_by: str) -> dict[str, Any]:
    cleaned_name = name.strip()
    if not cleaned_name:
        raise LlmPresetsError("invalid_name")
    if not is_valid_provider_model(provider, model_id):
        raise LlmPresetsError("invalid_provider_model")

    preset_id = uuid.uuid4().hex
    now = utc_now_iso()
    token_path = preset_token_path(preset_id)
    row = LlmPreset(
        id=preset_id,
        name=cleaned_name,
        provider=provider,
        model_id=model_id,
        oauth_token_path=str(token_path),
        oauth_account_label=None,
        created_at=now,
        updated_at=now,
        updated_by=updated_by,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _preset_to_dict(row)


def update_preset(
    db: Session,
    preset_id: str,
    *,
    name: str | None = None,
    model_id: str | None = None,
    updated_by: str,
) -> dict[str, Any]:
    row = get_preset(db, preset_id)
    if name is not None:
        cleaned = name.strip()
        if not cleaned:
            raise LlmPresetsError("invalid_name")
        row.name = cleaned
    if model_id is not None:
        if not is_valid_provider_model(row.provider, model_id):
            raise LlmPresetsError("invalid_provider_model")
        row.model_id = model_id
    row.updated_at = utc_now_iso()
    row.updated_by = updated_by
    db.commit()
    db.refresh(row)
    _bust_llm_caches()
    return _preset_to_dict(row)


def delete_preset(db: Session, preset_id: str) -> None:
    row = get_preset(db, preset_id)
    bindings = db.scalars(select(LlmSlotBinding).where(LlmSlotBinding.preset_id == preset_id)).all()
    if bindings:
        raise LlmPresetsError("preset_in_use", status_code=409)

    token_path = Path(row.oauth_token_path)
    db.delete(row)
    db.commit()
    if token_path.exists():
        token_path.unlink()
    _bust_llm_caches()


def mark_preset_oauth(db: Session, preset_id: str, account_label: str | None, updated_by: str) -> dict[str, Any]:
    row = get_preset(db, preset_id)
    row.oauth_account_label = (account_label or "").strip() or None
    row.updated_at = utc_now_iso()
    row.updated_by = updated_by
    db.commit()
    db.refresh(row)
    _bust_llm_caches()
    return _preset_to_dict(row)


def list_bindings(db: Session) -> list[dict[str, Any]]:
    rows = {row.slot: row for row in db.scalars(select(LlmSlotBinding)).all()}
    presets = {row.id: row for row in db.scalars(select(LlmPreset)).all()}
    out: list[dict[str, Any]] = []
    for slot in LLM_SLOTS:
        slot_id = slot["id"]
        binding = rows.get(slot_id)
        preset = presets.get(binding.preset_id) if binding and binding.preset_id else None
        out.append(
            {
                "slot": slot_id,
                "label": slot["label"],
                "description": slot.get("description", ""),
                "allow_inherit": bool(slot.get("allow_inherit")),
                "binding_type": binding.binding_type if binding else ("inherit" if slot.get("allow_inherit") else "preset"),
                "preset_id": binding.preset_id if binding else None,
                "preset": _preset_to_dict(preset) if preset else None,
            }
        )
    return out


def update_binding(
    db: Session,
    slot: str,
    *,
    binding_type: str,
    preset_id: str | None,
    updated_by: str,
) -> dict[str, Any]:
    slot_ids = {row["id"] for row in LLM_SLOTS}
    if slot not in slot_ids:
        raise LlmPresetsError("invalid_slot")
    if binding_type not in {"inherit", "preset"}:
        raise LlmPresetsError("invalid_binding_type")
    slot_meta = next(row for row in LLM_SLOTS if row["id"] == slot)
    if binding_type == "inherit" and not slot_meta.get("allow_inherit"):
        raise LlmPresetsError("inherit_not_allowed")
    if binding_type == "preset":
        if not preset_id:
            raise LlmPresetsError("preset_required")
        get_preset(db, preset_id)

    now = utc_now_iso()
    row = db.get(LlmSlotBinding, slot)
    if row is None:
        row = LlmSlotBinding(
            slot=slot,
            binding_type=binding_type,
            preset_id=preset_id if binding_type == "preset" else None,
            updated_at=now,
            updated_by=updated_by,
        )
        db.add(row)
    else:
        row.binding_type = binding_type
        row.preset_id = preset_id if binding_type == "preset" else None
        row.updated_at = now
        row.updated_by = updated_by
    db.commit()
    _bust_llm_caches()
    return next(item for item in list_bindings(db) if item["slot"] == slot)


def resolve_preset_for_slot(db: Session, slot: str) -> LlmPreset | None:
    ensure_legacy_migration(db)
    binding = db.get(LlmSlotBinding, slot)
    if binding is None:
        if slot == "chat":
            return _legacy_chat_preset(db)
        return None

    preset_id = binding.preset_id
    if binding.binding_type == "inherit" or not preset_id:
        if slot == "chat":
            return None
        return resolve_preset_for_slot(db, "chat")

    return db.get(LlmPreset, preset_id)


def _legacy_chat_preset(db: Session) -> LlmPreset | None:
    from app.secrets_admin import get_effective_secret

    settings = get_settings()
    auth_mode = get_effective_secret(db, "chat_auth_mode") or settings.LLM_AUTH_MODE
    if auth_mode != "chatgpt_oauth":
        return None
    legacy_path = Path(settings.codex_oauth_auth_path)
    if not oauth_tokens_configured(legacy_path):
        return None
    row = db.scalar(select(LlmPreset).where(LlmPreset.name == "__legacy_chatgpt_oauth__"))
    return row


def ensure_legacy_migration(db: Session) -> None:
    if db.scalar(select(LlmPreset.id).limit(1)) is not None:
        return

    from app.secrets_admin import get_effective_secret

    settings = get_settings()
    auth_mode = get_effective_secret(db, "chat_auth_mode") or settings.LLM_AUTH_MODE
    legacy_path = Path(settings.codex_oauth_auth_path)
    now = utc_now_iso()

    preset: LlmPreset | None = None
    if auth_mode == "chatgpt_oauth" and legacy_path.exists() and legacy_path.stat().st_size > 10:
        preset_id = uuid.uuid4().hex
        target = preset_token_path(preset_id)
        shutil.copy2(legacy_path, target)
        preset = LlmPreset(
            id=preset_id,
            name="ChatGPT OAuth (Legacy)",
            provider="openai",
            model_id=settings.CHAT_MODEL if settings.CHAT_MODEL.startswith("gpt-5") else "gpt-5.4-mini",
            oauth_token_path=str(target),
            oauth_account_label=None,
            created_at=now,
            updated_at=now,
            updated_by="system",
        )
        try:
            import json

            data = json.loads(target.read_text(encoding="utf-8"))
            preset.oauth_account_label = data.get("account_id")
            preset.oauth_token = json.dumps(data, ensure_ascii=True)
        except Exception:
            pass
        db.add(preset)

    db.flush()

    chat_binding = LlmSlotBinding(
        slot="chat",
        binding_type="preset",
        preset_id=preset.id if preset else None,
        updated_at=now,
        updated_by="system",
    )
    db.add(chat_binding)

    for slot in ("vision", "similarity", "kc_refine"):
        db.add(
            LlmSlotBinding(
                slot=slot,
                binding_type="inherit",
                preset_id=None,
                updated_at=now,
                updated_by="system",
            )
        )
    db.commit()


def _bust_llm_caches() -> None:
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


def get_assignments_status(db: Session) -> dict[str, Any]:
    from app.secrets_admin import _mask_value, get_effective_secret

    ensure_legacy_migration(db)
    emb_key = get_effective_secret(db, "embedding_api_key")
    integ = get_effective_secret(db, "integration_api_token") or ""
    return {
        "catalog": get_catalog(),
        "presets": list_presets(db),
        "bindings": list_bindings(db),
        "embedding": {"api_key_masked": _mask_value(emb_key)},
        "integration": {
            "api_key_masked": _mask_value(integ) if integ else "",
            "enabled": bool(integ.strip()),
        },
    }

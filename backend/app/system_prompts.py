from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.customers import is_global_customer
from app.models import SystemPrompt, utc_now_iso
from app.prompts import DEFAULT_GLOBAL_SYSTEM_PROMPT, GLOBAL_MODE_HINT, MARKDOWN_FORMATTING_HINT

GLOBAL_PROMPT_SCOPE = "__global__"


def _scope_key(customer_id: str | None) -> str:
    return GLOBAL_PROMPT_SCOPE if not customer_id else customer_id


def get_system_prompt(db: Session, customer_id: str | None) -> str | None:
    row = db.get(SystemPrompt, _scope_key(customer_id))
    if row is None or not row.content.strip():
        return None
    return row.content.strip()


def get_effective_system_prompt(db: Session, customer_id: str) -> str:
    parts: list[str] = []
    global_prompt = get_system_prompt(db, None)
    if global_prompt:
        parts.append(global_prompt)
    if customer_id and not is_global_customer(customer_id):
        customer_prompt = get_system_prompt(db, customer_id)
        if customer_prompt:
            parts.append(customer_prompt)
    if not parts:
        parts.append(DEFAULT_GLOBAL_SYSTEM_PROMPT)
    if is_global_customer(customer_id):
        parts.append(GLOBAL_MODE_HINT)
    parts.append(MARKDOWN_FORMATTING_HINT)
    return "\n\n".join(parts)


def set_system_prompt(
    db: Session,
    customer_id: str | None,
    content: str,
    *,
    updated_by: str,
) -> SystemPrompt:
    key = _scope_key(customer_id)
    now = utc_now_iso()
    row = db.get(SystemPrompt, key)
    cleaned = content.strip()
    if row is None:
        row = SystemPrompt(
            scope=key,
            customer_id=customer_id,
            content=cleaned,
            updated_at=now,
            updated_by=updated_by,
        )
        db.add(row)
    else:
        row.content = cleaned
        row.updated_at = now
        row.updated_by = updated_by
    db.commit()
    db.refresh(row)
    return row


def ensure_default_global_prompt(db: Session, updated_by: str = "system") -> None:
    if get_system_prompt(db, None) is not None:
        return
    set_system_prompt(db, None, DEFAULT_GLOBAL_SYSTEM_PROMPT, updated_by=updated_by)


def list_prompt_scopes(db: Session) -> list[SystemPrompt]:
    return list(db.scalars(select(SystemPrompt).order_by(SystemPrompt.scope)))

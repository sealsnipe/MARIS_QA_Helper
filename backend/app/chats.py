from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChatMessage, ChatSession, utc_now_iso
from app.retrieval import filter_sources_by_answer_citations


class ChatNotFoundError(Exception):
    pass


class ChatForbiddenError(Exception):
    pass


def _truncate_title(text: str, limit: int = 72) -> str:
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return "Neuer Chat"
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def create_session(db: Session, user_id: str, customer_id: str, *, title: str = "Neuer Chat") -> ChatSession:
    now = utc_now_iso()
    session = ChatSession(
        id=str(uuid.uuid4()),
        user_id=user_id,
        customer_id=customer_id,
        title=title,
        created_at=now,
        updated_at=now,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session_for_user(
    db: Session,
    chat_id: str,
    user_id: str,
    customer_id: str,
) -> ChatSession:
    session = db.get(ChatSession, chat_id)
    if session is None:
        raise ChatNotFoundError()
    if session.user_id != user_id or session.customer_id != customer_id:
        raise ChatForbiddenError()
    return session


def list_sessions(db: Session, user_id: str, customer_id: str) -> list[ChatSession]:
    stmt = (
        select(ChatSession)
        .where(ChatSession.user_id == user_id, ChatSession.customer_id == customer_id)
        .order_by(ChatSession.updated_at.desc())
    )
    return list(db.scalars(stmt))


def session_to_dict(session: ChatSession) -> dict[str, Any]:
    return {
        "id": session.id,
        "customer_id": session.customer_id,
        "title": session.title,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


def list_messages(db: Session, chat_id: str) -> list[dict[str, Any]]:
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == chat_id)
        .order_by(ChatMessage.created_at.asc())
    )
    rows = list(db.scalars(stmt))
    return [message_to_dict(row) for row in rows]


def message_to_dict(message: ChatMessage) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    if message.sources_json:
        try:
            sources = json.loads(message.sources_json)
        except json.JSONDecodeError:
            sources = []
    if message.role == "assistant" and sources and message.content:
        sources = filter_sources_by_answer_citations(sources, message.content)
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "sources": sources,
        "no_context": bool(message.no_context),
        "created_at": message.created_at,
    }


def add_message(
    db: Session,
    session: ChatSession,
    role: str,
    content: str,
    *,
    sources: list[dict[str, Any]] | None = None,
    no_context: bool = False,
) -> ChatMessage:
    now = utc_now_iso()
    message = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=session.id,
        role=role,
        content=content,
        sources_json=json.dumps(sources or [], ensure_ascii=False) if role == "assistant" else None,
        no_context=1 if no_context else 0,
        created_at=now,
    )
    session.updated_at = now
    if role == "user" and (not session.title or session.title == "Neuer Chat"):
        session.title = _truncate_title(content)
    db.add(message)
    db.commit()
    db.refresh(message)
    db.refresh(session)
    return message


def delete_session(db: Session, chat_id: str, user_id: str, customer_id: str) -> bool:
    session = get_session_for_user(db, chat_id, user_id, customer_id)
    db.delete(session)
    db.commit()
    return True

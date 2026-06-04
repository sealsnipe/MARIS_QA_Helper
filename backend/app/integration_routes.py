from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent import AgentError, run as run_agent
from app.chats import (
    ChatForbiddenError,
    ChatNotFoundError,
    add_message,
    create_session,
    get_session_for_user,
)
from app.customers import get_customer, is_customer_active
from app.db import get_db
from app.integration_auth import get_integration_user
from app.models import Customer, User
from app.retrieval import filter_sources_by_answer_citations

router = APIRouter(tags=["Integration"])


class IntegrationAskRequest(BaseModel):
    question: str = Field(min_length=1)
    customer_id: str = Field(min_length=1, max_length=64)
    chat_id: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)


def _require_active_customer(db: Session, customer_id: str) -> Customer | JSONResponse:
    customer = get_customer(db, customer_id.strip())
    if customer is None or not is_customer_active(customer):
        return JSONResponse({"error": "forbidden_customer"}, status_code=403)
    return customer


@router.post("/api/v1/ask")
def api_v1_ask(
    payload: IntegrationAskRequest,
    user: User = Depends(get_integration_user),
    db: Session = Depends(get_db),
):
    question = payload.question.strip()
    if not question:
        return JSONResponse({"error": "empty_question"}, status_code=400)

    customer = _require_active_customer(db, payload.customer_id)
    if isinstance(customer, JSONResponse):
        return customer

    try:
        if payload.chat_id:
            session = get_session_for_user(db, payload.chat_id, user.id, customer.id)
        else:
            session = create_session(db, user.id, customer.id)
    except ChatNotFoundError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except ChatForbiddenError:
        return JSONResponse({"error": "forbidden_customer"}, status_code=403)

    add_message(db, session, "user", question)

    try:
        result = run_agent(
            customer.id,
            question,
            top_k=payload.top_k,
            db=db,
            scope_customer_ids=[customer.id],
        )
    except AgentError:
        raise

    filtered_sources = filter_sources_by_answer_citations(result.sources, result.answer)

    add_message(
        db,
        session,
        "assistant",
        result.answer,
        sources=filtered_sources,
        no_context=result.no_context,
    )

    return {
        "answer": result.answer,
        "sources": filtered_sources,
        "no_context": result.no_context,
        "chat_id": session.id,
        "customer_id": customer.id,
    }

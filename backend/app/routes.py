from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent import AgentError, run as run_agent
from app.chats import (
    ChatForbiddenError,
    ChatNotFoundError,
    add_message,
    create_session,
    delete_session,
    get_session_for_user,
    list_messages,
    list_sessions,
    session_to_dict,
)
from app.auth import (
    ForbiddenError,
    NotAuthenticatedError,
    get_admin_user,
    get_current_user,
    get_user_by_email,
    verify_password,
)
from app.customers import (
    DEMO_CUSTOMER_IDS,
    GLOBAL_CUSTOMER_ID,
    get_customer,
    is_global_customer,
    list_assigned_customer_ids,
    list_customers_for_nav,
    list_customers_for_user,
    list_production_customers,
    user_has_customer,
)
from app.db import get_db
from app.ingestion import IngestionError, delete_document, ingest_text, list_documents, list_documents_for_customers
from app.models import Customer, User
from app.tenant import (
    CustomerNotFoundError,
    ForbiddenCustomerError,
    get_current_customer,
)
from app.system_prompts import get_system_prompt, set_system_prompt
from app.retrieval import filter_sources_by_answer_citations

from app.upload import UploadError, ingest_combined

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


class CustomerSwitchRequest(BaseModel):
    customer_id: str = Field(min_length=1)


class TextDocumentRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)
    chat_id: str | None = None


class SystemPromptRequest(BaseModel):
    customer_id: str | None = None
    content: str = Field(min_length=1)


def _page_context(
    request: Request,
    user: User,
    db: Session,
    *,
    active_page: str,
) -> dict:
    customers = list_customers_for_nav(db, user.id)
    active_customer_id = request.session.get("customer_id")
    active_customer = get_customer(db, active_customer_id) if active_customer_id else None
    admin_customers = list_production_customers(db)
    return {
        "user": user,
        "customers": customers,
        "admin_customers": admin_customers,
        "active_customer": active_customer,
        "is_admin": bool(user.is_admin),
        "active_page": active_page,
        "global_customer_id": GLOBAL_CUSTOMER_ID,
        "customer_labels": {customer.id: customer.name for customer in customers},
    }


def _document_payload(document) -> dict:
    return {
        "id": document.id,
        "customer_id": document.customer_id,
        "title": document.title,
        "source_type": document.source_type,
        "original_filename": document.original_filename,
        "mime_type": document.mime_type,
        "chunk_count": document.chunk_count,
        "status": document.status,
        "error_message": getattr(document, "error_message", None),
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }


@router.get("/api/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request, error: str | None = None) -> HTMLResponse:
    if request.session.get("user_id"):
        return RedirectResponse(url="/chat", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": error},
    )


@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    user = get_user_by_email(db, email)
    if user is None or not verify_password(user.password_hash, password):
        return RedirectResponse(
            url="/login?error=1",
            status_code=status.HTTP_302_FOUND,
        )

    request.session.clear()
    request.session["user_id"] = user.id

    customers = list_customers_for_user(db, user.id)
    if len(customers) == 1:
        request.session["customer_id"] = customers[0].id

    return RedirectResponse(url="/chat", status_code=status.HTTP_302_FOUND)


@router.post("/logout")
def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)


@router.get("/", response_class=RedirectResponse)
def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/chat", status_code=status.HTTP_302_FOUND)


@router.get("/chat", response_class=HTMLResponse)
def chat_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "chat.html",
        _page_context(request, user, db, active_page="chat"),
    )


@router.get("/kb", response_class=HTMLResponse)
def kb_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "kb.html",
        _page_context(request, user, db, active_page="kb"),
    )


@router.get("/admin", response_class=HTMLResponse)
def admin_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    if not user.is_admin:
        return RedirectResponse(url="/chat", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        request,
        "admin.html",
        _page_context(request, user, db, active_page="admin"),
    )


@router.get("/api/customers")
def api_list_customers(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    customers = list_customers_for_nav(db, user.id)
    return {
        "customers": [{"id": customer.id, "name": customer.name} for customer in customers],
        "active": request.session.get("customer_id"),
    }


@router.post("/api/session/customer")
def api_set_customer(
    payload: CustomerSwitchRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    customer_id = payload.customer_id.strip()
    customer = get_customer(db, customer_id)
    if customer is None:
        raise CustomerNotFoundError()

    if not user_has_customer(db, user.id, customer_id):
        raise ForbiddenCustomerError()

    request.session["customer_id"] = customer_id
    return JSONResponse({"active": customer_id})


@router.get("/api/me")
def api_me(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Protected JSON route for auth smoke tests."""
    return {
        "user_id": user.id,
        "email": user.email,
        "is_admin": bool(user.is_admin),
        "active_customer": request.session.get("customer_id"),
    }


@router.get("/api/tenant-check")
def api_tenant_check(
    customer=Depends(get_current_customer),
) -> dict:
    """Protected tenant-scoped JSON route for M2 tests."""
    return {"customer_id": customer.id, "customer_name": customer.name}


def _documents_for_scope(db: Session, user: User, customer: Customer) -> list[dict]:
    if is_global_customer(customer.id):
        scope_ids = [GLOBAL_CUSTOMER_ID, *list_assigned_customer_ids(db, user.id)]
        return list_documents_for_customers(db, scope_ids)
    return list_documents(db, customer.id)


def _reject_global_write(customer: Customer) -> JSONResponse | None:
    if is_global_customer(customer.id):
        return JSONResponse(
            {
                "error": "read_only_scope",
                "detail": "Im Global-Modus ist die Wissensdatenbank nur lesbar. Bearbeiten nur über Administration.",
            },
            status_code=403,
        )
    return None


@router.get("/api/documents")
def api_list_documents(
    user: User = Depends(get_current_user),
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> dict:
    return {
        "customer_id": customer.id,
        "read_only": is_global_customer(customer.id),
        "documents": _documents_for_scope(db, user, customer),
    }


@router.post("/api/documents/text")
def api_create_text_document(
    payload: TextDocumentRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> dict:
    if blocked := _reject_global_write(customer):
        return blocked
    try:
        result = ingest_text(
            db,
            customer_id=customer.id,
            title=payload.title,
            text=payload.text,
            source_type="manual",
        )
    except IngestionError:
        raise
    return {"document": _document_payload(result.document)}


@router.post("/api/documents")
async def api_upload_document(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
    title: str | None = Form(default=None),
    text: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
) -> dict:
    if blocked := _reject_global_write(customer):
        return blocked
    content: bytes | None = None
    filename: str | None = None
    if file is not None and file.filename:
        content = await file.read()
        filename = file.filename

    try:
        document = ingest_combined(
            db,
            customer_id=customer.id,
            title=title,
            prefix_text=text,
            filename=filename,
            content=content,
            mime_type=file.content_type if file else None,
        )
    except UploadError:
        raise
    return {"document": _document_payload(document)}


@router.post("/api/chat")
def api_chat(
    payload: ChatRequest,
    user: User = Depends(get_current_user),
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    message = payload.message.strip()
    if not message:
        return JSONResponse({"error": "empty_message"}, status_code=400)

    try:
        if payload.chat_id:
            session = get_session_for_user(db, payload.chat_id, user.id, customer.id)
        else:
            session = create_session(db, user.id, customer.id)
    except ChatNotFoundError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except ChatForbiddenError:
        return JSONResponse({"error": "forbidden_customer"}, status_code=403)

    add_message(db, session, "user", message)

    try:
        result = run_agent(
            customer.id,
            message,
            top_k=payload.top_k,
            db=db,
            scope_customer_ids=list_assigned_customer_ids(db, user.id),
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
        "chat_id": session.id,
        "chat_title": session.title,
        "customer_id": customer.id,
        "answer": result.answer,
        "sources": filtered_sources,
        "no_context": result.no_context,
    }


@router.get("/api/chats")
def api_list_chats(
    user: User = Depends(get_current_user),
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> dict:
    sessions = list_sessions(db, user.id, customer.id)
    return {
        "customer_id": customer.id,
        "chats": [session_to_dict(item) for item in sessions],
    }


@router.post("/api/chats")
def api_create_chat(
    user: User = Depends(get_current_user),
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> dict:
    session = create_session(db, user.id, customer.id)
    return {"chat": session_to_dict(session)}


@router.get("/api/chats/{chat_id}")
def api_get_chat(
    chat_id: str,
    user: User = Depends(get_current_user),
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    try:
        session = get_session_for_user(db, chat_id, user.id, customer.id)
    except ChatNotFoundError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except ChatForbiddenError:
        return JSONResponse({"error": "forbidden_customer"}, status_code=403)

    return {
        "chat": session_to_dict(session),
        "messages": list_messages(db, session.id),
    }


@router.delete("/api/chats/{chat_id}")
def api_delete_chat(
    chat_id: str,
    user: User = Depends(get_current_user),
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> JSONResponse:
    try:
        delete_session(db, chat_id, user.id, customer.id)
    except ChatNotFoundError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except ChatForbiddenError:
        return JSONResponse({"error": "forbidden_customer"}, status_code=403)
    return JSONResponse({"deleted": True, "id": chat_id})


@router.delete("/api/documents/{document_id}")
def api_delete_document(
    document_id: str,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> JSONResponse:
    if blocked := _reject_global_write(customer):
        return blocked
    deleted = delete_document(db, customer.id, document_id)
    if not deleted:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return JSONResponse({"deleted": True, "id": document_id})


@router.get("/api/admin/system-prompt")
def api_get_system_prompt(
    customer_id: str | None = None,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    scope = None if not customer_id or customer_id == "global" else customer_id
    if scope in DEMO_CUSTOMER_IDS:
        return JSONResponse({"error": "forbidden_customer"}, status_code=403)
    content = get_system_prompt(db, scope) or ""
    return {"customer_id": scope, "content": content}


@router.put("/api/admin/system-prompt")
def api_put_system_prompt(
    payload: SystemPromptRequest,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    scope = payload.customer_id
    if scope == "global":
        scope = None
    if scope:
        if scope in DEMO_CUSTOMER_IDS:
            return JSONResponse({"error": "forbidden_customer"}, status_code=403)
        customer = get_customer(db, scope)
        if customer is None or scope == GLOBAL_CUSTOMER_ID:
            raise CustomerNotFoundError()
    row = set_system_prompt(db, scope, payload.content, updated_by=admin.email)
    return {
        "customer_id": row.customer_id,
        "content": row.content,
        "updated_at": row.updated_at,
    }


@router.get("/api/admin/documents")
def api_admin_list_documents(
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    return {
        "customer_id": GLOBAL_CUSTOMER_ID,
        "documents": list_documents(db, GLOBAL_CUSTOMER_ID),
    }


@router.post("/api/admin/documents")
async def api_admin_upload_document(
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    title: str | None = Form(default=None),
    text: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
) -> dict:
    content: bytes | None = None
    filename: str | None = None
    if file is not None and file.filename:
        content = await file.read()
        filename = file.filename

    try:
        document = ingest_combined(
            db,
            customer_id=GLOBAL_CUSTOMER_ID,
            title=title,
            prefix_text=text,
            filename=filename,
            content=content,
            mime_type=file.content_type if file else None,
        )
    except UploadError:
        raise
    return {"document": _document_payload(document)}


@router.delete("/api/admin/documents/{document_id}")
def api_admin_delete_document(
    document_id: str,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    deleted = delete_document(db, GLOBAL_CUSTOMER_ID, document_id)
    if not deleted:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return JSONResponse({"deleted": True, "id": document_id})

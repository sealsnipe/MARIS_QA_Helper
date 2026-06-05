from pathlib import Path
import json

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
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
    GLOBAL_CUSTOMER_ID,
    create_tenant_customer,
    customer_to_dict,
    deactivate_tenant_customer,
    get_customer,
    is_global_customer,
    list_assigned_customer_ids,
    list_customers_for_nav,
    list_customers_for_user,
    list_tenant_customers,
    rename_tenant_customer,
    update_tenant_customer,
    user_has_customer,
)
from app.db import get_db
from app.document_assets import image_payloads, resolve_document_image_path
from app.llm import LLMError, transcribe_image
from app.loaders.image_inspect import MIN_IMAGE_BYTES
from app.loaders.vision_ocr import OCR_PROMPT
from app.chunking import normalize_text
from app.config import get_settings
from app.ingestion import (
    IngestionError,
    delete_document,
    get_document,
    get_document_text,
    ingest_text,
    list_documents,
    list_documents_for_customers,
    update_document_content,
)
from app.models import Customer, User
from app.tenant import (
    CustomerNotFoundError,
    ForbiddenCustomerError,
    get_current_customer,
)
from app.system_prompts import get_system_prompt, set_system_prompt
from app.retrieval import filter_sources_by_answer_citations

from app.upload import (
    UploadError,
    ingest_combined,
    inspect_text_content,
    inspect_upload,
    parse_form_bool,
    resolve_upload_source_text,
)
from app.document_merge import MergeError, apply_document_merge, merge_preview_for_documents
from app.users_admin import (
    UserAdminError,
    create_admin_user,
    deactivate_admin_user,
    list_admin_users,
    list_assignable_customers,
    update_admin_user,
    user_to_dict,
)
from app.roles_admin import (
    RoleAdminError,
    create_admin_role,
    delete_admin_role,
    list_admin_roles,
    role_to_dict,
    update_admin_role,
)
from app.secrets_admin import (
    SecretsAdminError,
    get_effective_secret,
    get_keys_status,
    update_secret,
)
from app.knowledge_center import (
    KnowledgeCenterError,
    adopt_knowledge_content,
    content_to_dict,
    create_knowledge_source,
    delete_knowledge_source,
    get_knowledge_content_for_user,
    list_adoptable_customers,
    list_knowledge_contents,
    list_knowledge_sources,
    reject_knowledge_content,
    source_to_dict,
    update_knowledge_source,
)

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


class AdminCustomerCreateRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)


class AdminCustomerUpdateRequest(BaseModel):
    id: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=200)


class AdminUserCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=8, max_length=200)
    customer_ids: list[str] = Field(default_factory=list)
    role_ids: list[str] = Field(default_factory=list)
    is_admin: bool = False


class AdminUserUpdateRequest(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=200)
    password: str | None = Field(default=None, min_length=8, max_length=200)
    customer_ids: list[str] | None = None
    role_ids: list[str] | None = None
    is_admin: bool | None = None
    is_active: bool | None = None


class AdminRoleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    customer_ids: list[str] = Field(default_factory=list)
    is_admin: bool = False
    auto_add_new_customers: bool = False


class AdminRoleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    customer_ids: list[str] | None = None
    is_admin: bool | None = None
    auto_add_new_customers: bool | None = None


class AdminKeysChatUpdate(BaseModel):
    auth_mode: str | None = None
    api_key: str | None = None


class AdminKeysEmbeddingUpdate(BaseModel):
    api_key: str | None = None


class AdminKeysSimilarityUpdate(BaseModel):
    mode: str | None = None
    auth_mode: str | None = None
    api_key: str | None = None


class AdminKeysIntegrationUpdate(BaseModel):
    api_key: str | None = None


class AdminKnowledgeSourceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    host_code: str = Field(min_length=1, max_length=64)


class AdminKnowledgeSourceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    active: bool | None = None


class KnowledgeContentAdoptRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=64)


class DocumentUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1)


def _merge_error_response(exc: MergeError) -> JSONResponse:
    if exc.code == "not_found":
        status_code = 404
    elif exc.code in {"llm_failed", "llm_invalid_response", "llm_empty_response", "llm_disabled"}:
        status_code = 422
    else:
        status_code = 400
    payload: dict = {"error": exc.code}
    if exc.detail:
        payload["detail"] = exc.detail
    return JSONResponse(payload, status_code=status_code)


async def _read_merge_source_text(
    *,
    prefix_text: str | None,
    file: UploadFile | None,
) -> tuple[str | None, JSONResponse | None]:
    content: bytes | None = None
    filename: str | None = None
    if file is not None and file.filename:
        content = await file.read()
        filename = file.filename
    try:
        combined = resolve_upload_source_text(
            prefix_text=prefix_text,
            filename=filename,
            content=content,
        )
    except UploadError as exc:
        return None, JSONResponse({"error": exc.code}, status_code=400)
    if len(normalize_text(combined)) < 20:
        return None, JSONResponse({"error": "empty_text"}, status_code=400)
    return combined, None


def _admin_page_redirect(user: User) -> RedirectResponse | None:
    if not user.is_admin:
        return RedirectResponse(url="/chat", status_code=status.HTTP_302_FOUND)
    return None


# Sidebar customer dropdown: scoped (chat/kb), admin_scoped (KB/prompts admin), global (no page effect).
CUSTOMER_NAV_SCOPED_PAGES = frozenset({"chat", "kb", "tools_bild_zu_text"})
CUSTOMER_NAV_ADMIN_SCOPED_PAGES = frozenset({"admin_knowledge", "admin_prompts"})
CUSTOMER_NAV_GLOBAL_PAGES = frozenset({
    "customers",
    "admin_users",
    "admin_roles",
    "admin_keys",
    "tools_kc_content",
    "tools_kc_sources",
})


def customer_nav_mode(active_page: str) -> str:
    if active_page in CUSTOMER_NAV_GLOBAL_PAGES:
        return "global"
    if active_page in CUSTOMER_NAV_ADMIN_SCOPED_PAGES:
        return "admin_scoped"
    if active_page in CUSTOMER_NAV_SCOPED_PAGES:
        return "scoped"
    return "scoped"


def _page_context(
    request: Request,
    user: User,
    db: Session,
    *,
    active_page: str,
) -> dict:
    customers = list_customers_for_nav(db, user)
    active_customer_id = request.session.get("customer_id")
    active_customer = get_customer(db, active_customer_id) if active_customer_id else None
    admin_customers = list_tenant_customers(db)
    nav_mode = customer_nav_mode(active_page)
    return {
        "user": user,
        "customers": customers,
        "admin_customers": admin_customers,
        "active_customer": active_customer,
        "is_admin": bool(user.is_admin),
        "active_page": active_page,
        "customer_nav_mode": nav_mode,
        "global_customer_id": GLOBAL_CUSTOMER_ID,
        "customer_labels": {customer.id: customer.name for customer in customers},
    }


def _document_payload(document) -> dict:
    meta = None
    raw_meta = getattr(document, "extraction_meta", None)
    if raw_meta:
        try:
            parsed = json.loads(raw_meta)
            meta = parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            meta = None
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
        "extraction_meta": meta,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }


def _admin_document_detail(
    db: Session,
    customer_id: str,
    document_id: str,
    *,
    assets_base_path: str,
) -> dict | None:
    loaded = get_document_text(db, customer_id, document_id)
    if loaded is None:
        return None
    document, text = loaded
    editable = bool(text.strip()) or document.status != "failed"
    return {
        "document": _document_payload(document),
        "text": text,
        "editable": editable,
        "from_file": bool(document.storage_path),
        "images": image_payloads(document, base_url=assets_base_path),
    }


def _document_image_file_response(document, image_id: str) -> Response:
    path = resolve_document_image_path(document, image_id)
    if path is None:
        return JSONResponse({"error": "not_found"}, status_code=404)
    media_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, media_type=media_type)


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
    if user.is_admin:
        return RedirectResponse(url="/admin/knowledge", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        request,
        "kb.html",
        _page_context(request, user, db, active_page="kb"),
    )


@router.get("/tools/bild-zu-text", response_class=HTMLResponse)
def tools_bild_zu_text_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "tools/bild_zu_text.html",
        _page_context(request, user, db, active_page="tools_bild_zu_text"),
    )


@router.get("/tools/knowledge-center", response_class=HTMLResponse)
def tools_knowledge_center_content_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "tools/knowledge_center_content.html",
        _page_context(request, user, db, active_page="tools_kc_content"),
    )


@router.get("/tools/knowledge-center/sources", response_class=HTMLResponse)
def tools_knowledge_center_sources_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    if redirect := _admin_page_redirect(user):
        return redirect
    return templates.TemplateResponse(
        request,
        "tools/knowledge_center_sources.html",
        _page_context(request, user, db, active_page="tools_kc_sources"),
    )


@router.get("/admin", response_class=HTMLResponse)
def admin_page(
    user: User = Depends(get_current_user),
) -> RedirectResponse:
    if redirect := _admin_page_redirect(user):
        return redirect
    return RedirectResponse(url="/admin/customers", status_code=status.HTTP_302_FOUND)


@router.get("/admin/customers", response_class=HTMLResponse)
def admin_customers_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    if redirect := _admin_page_redirect(user):
        return redirect
    return templates.TemplateResponse(
        request,
        "customers.html",
        _page_context(request, user, db, active_page="customers"),
    )


@router.get("/admin/knowledge", response_class=HTMLResponse)
def admin_knowledge_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    if redirect := _admin_page_redirect(user):
        return redirect
    return templates.TemplateResponse(
        request,
        "admin_knowledge.html",
        _page_context(request, user, db, active_page="admin_knowledge"),
    )


@router.get("/admin/prompts", response_class=HTMLResponse)
def admin_prompts_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    if redirect := _admin_page_redirect(user):
        return redirect
    return templates.TemplateResponse(
        request,
        "admin_prompts.html",
        _page_context(request, user, db, active_page="admin_prompts"),
    )


@router.get("/admin/users", response_class=HTMLResponse)
def admin_users_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    if redirect := _admin_page_redirect(user):
        return redirect
    return templates.TemplateResponse(
        request,
        "admin_users.html",
        _page_context(request, user, db, active_page="admin_users"),
    )


@router.get("/admin/roles", response_class=HTMLResponse)
def admin_roles_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    if redirect := _admin_page_redirect(user):
        return redirect
    return templates.TemplateResponse(
        request,
        "admin_roles.html",
        _page_context(request, user, db, active_page="admin_roles"),
    )


@router.get("/admin/keys", response_class=HTMLResponse)
def admin_keys_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    if redirect := _admin_page_redirect(user):
        return redirect
    return templates.TemplateResponse(
        request,
        "admin_keys.html",
        _page_context(request, user, db, active_page="admin_keys"),
    )


@router.get("/api/customers")
def api_list_customers(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    customers = list_customers_for_nav(db, user)
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


@router.post("/api/documents/inspect")
async def api_inspect_document(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    text: str | None = Form(default=None),
) -> dict:
    if blocked := _reject_global_write(customer):
        return blocked
    if not file.filename:
        return JSONResponse({"error": "unsupported_file_type"}, status_code=400)
    content = await file.read()
    try:
        return inspect_upload(db, customer.id, content, file.filename, prefix_text=text)
    except UploadError as exc:
        return JSONResponse({"error": exc.code}, status_code=400 if exc.code != "inspection_failed" else 422)


@router.post("/api/documents")
async def api_upload_document(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
    title: str | None = Form(default=None),
    text: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    process_images: str | None = Form(default=None),
    transcribe_image_ids: str | None = Form(default=None),
    allow_duplicate: str | None = Form(default=None),
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
            process_images=parse_form_bool(process_images),
            transcribe_image_ids_raw=transcribe_image_ids,
            allow_duplicate=parse_form_bool(allow_duplicate),
        )
    except UploadError:
        raise
    return {"document": _document_payload(document)}


@router.post("/api/documents/inspect-text")
async def api_inspect_document_text(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
    text: str = Form(...),
) -> dict:
    if blocked := _reject_global_write(customer):
        return blocked
    return inspect_text_content(db, customer.id, text)


@router.post("/api/documents/merge-preview")
async def api_merge_preview_document(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
    target_document_id: str = Form(...),
    text: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    use_llm: str | None = Form(default=None),
) -> dict:
    if blocked := _reject_global_write(customer):
        return blocked
    combined, error = await _read_merge_source_text(prefix_text=text, file=file)
    if error is not None:
        return error
    assert combined is not None
    try:
        return merge_preview_for_documents(
            db,
            customer.id,
            target_document_id,
            combined,
            use_llm=parse_form_bool(use_llm),
        )
    except MergeError as exc:
        return _merge_error_response(exc)


@router.post("/api/documents/{document_id}/merge")
async def api_merge_document(
    document_id: str,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
    blocks: str = Form(...),
    text: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    title: str | None = Form(default=None),
    merged_text: str | None = Form(default=None),
) -> dict:
    if blocked := _reject_global_write(customer):
        return blocked
    combined, error = await _read_merge_source_text(prefix_text=text, file=file)
    if error is not None:
        return error
    assert combined is not None
    try:
        parsed_blocks = json.loads(blocks)
    except json.JSONDecodeError:
        return JSONResponse({"error": "invalid_blocks"}, status_code=400)
    if not isinstance(parsed_blocks, list):
        return JSONResponse({"error": "invalid_blocks"}, status_code=400)
    try:
        result = apply_document_merge(
            db,
            customer.id,
            document_id,
            combined,
            parsed_blocks,
            title=title,
            merged_text_override=merged_text,
        )
    except MergeError as exc:
        return _merge_error_response(exc)
    return {"document": _document_payload(result["document"]), "stats": result["stats"]}


@router.post("/api/tools/transcribe")
async def api_tools_transcribe(
    user: User = Depends(get_current_user),
    files: list[UploadFile] = File(...),
) -> dict:
    """Standalone image transcription tool. Accepts one or more image files, returns OCR text for each using the configured Vision model."""
    settings = get_settings()
    if not settings.vision_enabled:
        return JSONResponse({"error": "vision_disabled"}, status_code=403)

    results: list[dict] = []
    for f in (files or [])[: settings.vision_max_images]:
        if not f or not f.filename:
            continue
        content = await f.read()
        mime = (f.content_type or "").lower()
        if not mime.startswith("image/"):
            results.append({"filename": f.filename, "error": "unsupported_file_type"})
            continue
        if len(content) < MIN_IMAGE_BYTES:
            results.append({"filename": f.filename, "error": "image_too_small"})
            continue
        try:
            text = transcribe_image(content, mime or "image/png", prompt=OCR_PROMPT).strip()
            results.append({
                "filename": f.filename,
                "mime_type": mime,
                "text": text,
            })
        except LLMError as exc:
            results.append({"filename": f.filename, "error": "transcription_failed", "detail": str(exc)})
        except Exception as exc:
            results.append({"filename": f.filename, "error": "transcription_failed", "detail": str(exc)})

    return {"results": results}


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


@router.get("/api/documents/{document_id}/images/{image_id}")
def api_get_document_image(
    document_id: str,
    image_id: str,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> Response:
    document = get_document(db, customer.id, document_id)
    if document is None:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return _document_image_file_response(document, image_id)


@router.get("/api/admin/system-prompt")
def api_get_system_prompt(
    customer_id: str | None = None,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    scope = None if not customer_id or customer_id == "global" else customer_id
    content = get_system_prompt(db, scope) or ""
    return {"customer_id": scope, "content": content}


@router.get("/api/admin/customers")
def api_admin_list_customers(
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    customers = list_tenant_customers(db)
    return {"customers": [customer_to_dict(customer) for customer in customers]}


@router.post("/api/admin/customers")
def api_admin_create_customer(
    payload: AdminCustomerCreateRequest,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    customer = create_tenant_customer(db, payload.customer_id, payload.name)
    return {"customer": customer_to_dict(customer)}


@router.patch("/api/admin/customers/{customer_id}")
def api_admin_update_customer(
    customer_id: str,
    payload: AdminCustomerUpdateRequest,
    request: Request,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    current_id = customer_id
    original_active = request.session.get("customer_id")
    # rename (id change) first if requested and different
    if payload.id is not None:
        new_slug = payload.id.strip().lower()
        if new_slug != customer_id:
            renamed = rename_tenant_customer(db, customer_id, new_slug)
            current_id = renamed.id
            # keep this admin's session consistent if they had the old slug active
            if original_active == customer_id:
                request.session["customer_id"] = current_id
    # then name (if provided)
    if payload.name is not None:
        updated = update_tenant_customer(db, current_id, payload.name)
        return {"customer": customer_to_dict(updated)}
    # id-only change or no-op
    cust = get_customer(db, current_id) or db.get(Customer, current_id)
    if cust is None:
        raise CustomerNotFoundError()
    return {"customer": customer_to_dict(cust)}


@router.delete("/api/admin/customers/{customer_id}")
def api_admin_delete_customer(
    customer_id: str,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    deactivate_tenant_customer(db, customer_id)
    return {"deleted": True, "id": customer_id}


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


@router.post("/api/admin/documents/inspect")
async def api_admin_inspect_document(
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    text: str | None = Form(default=None),
) -> dict:
    if not file.filename:
        return JSONResponse({"error": "unsupported_file_type"}, status_code=400)
    content = await file.read()
    try:
        return inspect_upload(db, GLOBAL_CUSTOMER_ID, content, file.filename, prefix_text=text)
    except UploadError as exc:
        return JSONResponse({"error": exc.code}, status_code=400 if exc.code != "inspection_failed" else 422)


@router.post("/api/admin/documents/inspect-text")
async def api_admin_inspect_document_text(
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    text: str = Form(...),
) -> dict:
    return inspect_text_content(db, GLOBAL_CUSTOMER_ID, text)


@router.post("/api/admin/documents/merge-preview")
async def api_admin_merge_preview_document(
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    target_document_id: str = Form(...),
    text: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    use_llm: str | None = Form(default=None),
) -> dict:
    combined, error = await _read_merge_source_text(prefix_text=text, file=file)
    if error is not None:
        return error
    assert combined is not None
    try:
        return merge_preview_for_documents(
            db,
            GLOBAL_CUSTOMER_ID,
            target_document_id,
            combined,
            use_llm=parse_form_bool(use_llm),
        )
    except MergeError as exc:
        return _merge_error_response(exc)


@router.post("/api/admin/documents/{document_id}/merge")
async def api_admin_merge_document(
    document_id: str,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    blocks: str = Form(...),
    text: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    title: str | None = Form(default=None),
    merged_text: str | None = Form(default=None),
) -> dict:
    combined, error = await _read_merge_source_text(prefix_text=text, file=file)
    if error is not None:
        return error
    assert combined is not None
    try:
        parsed_blocks = json.loads(blocks)
    except json.JSONDecodeError:
        return JSONResponse({"error": "invalid_blocks"}, status_code=400)
    if not isinstance(parsed_blocks, list):
        return JSONResponse({"error": "invalid_blocks"}, status_code=400)
    try:
        result = apply_document_merge(
            db,
            GLOBAL_CUSTOMER_ID,
            document_id,
            combined,
            parsed_blocks,
            title=title,
            merged_text_override=merged_text,
        )
    except MergeError as exc:
        return _merge_error_response(exc)
    return {"document": _document_payload(result["document"]), "stats": result["stats"]}


@router.post("/api/admin/documents")
async def api_admin_upload_document(
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    title: str | None = Form(default=None),
    text: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    process_images: str | None = Form(default=None),
    transcribe_image_ids: str | None = Form(default=None),
    allow_duplicate: str | None = Form(default=None),
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
            process_images=parse_form_bool(process_images),
            transcribe_image_ids_raw=transcribe_image_ids,
            allow_duplicate=parse_form_bool(allow_duplicate),
        )
    except UploadError:
        raise
    return {"document": _document_payload(document)}


@router.get("/api/admin/documents/{document_id}")
def api_admin_get_document(
    document_id: str,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    payload = _admin_document_detail(
        db,
        GLOBAL_CUSTOMER_ID,
        document_id,
        assets_base_path=f"/api/admin/documents/{document_id}",
    )
    if payload is None:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return payload


@router.get("/api/admin/documents/{document_id}/images/{image_id}")
def api_admin_get_document_image(
    document_id: str,
    image_id: str,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Response:
    document = get_document(db, GLOBAL_CUSTOMER_ID, document_id)
    if document is None:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return _document_image_file_response(document, image_id)


@router.put("/api/admin/documents/{document_id}")
def api_admin_update_document(
    document_id: str,
    body: DocumentUpdateRequest,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        result = update_document_content(
            db,
            GLOBAL_CUSTOMER_ID,
            document_id,
            body.title,
            body.text,
        )
    except IngestionError as exc:
        if exc.code == "not_found":
            return JSONResponse({"error": "not_found"}, status_code=404)
        raise
    return {"document": _document_payload(result.document)}


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


def _admin_tenant_customer(db: Session, customer_id: str) -> Customer:
    if is_global_customer(customer_id):
        raise CustomerNotFoundError()
    customer = get_customer(db, customer_id)
    if customer is None:
        raise CustomerNotFoundError()
    return customer


@router.get("/api/admin/customers/{customer_id}/documents")
def api_admin_list_customer_documents(
    customer_id: str,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    customer = _admin_tenant_customer(db, customer_id)
    return {
        "customer_id": customer.id,
        "documents": list_documents(db, customer.id),
    }


@router.post("/api/admin/customers/{customer_id}/documents/inspect")
async def api_admin_inspect_customer_document(
    customer_id: str,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    text: str | None = Form(default=None),
) -> dict:
    _admin_tenant_customer(db, customer_id)
    if not file.filename:
        return JSONResponse({"error": "unsupported_file_type"}, status_code=400)
    content = await file.read()
    try:
        return inspect_upload(db, customer_id, content, file.filename, prefix_text=text)
    except UploadError as exc:
        return JSONResponse({"error": exc.code}, status_code=400 if exc.code != "inspection_failed" else 422)


@router.post("/api/admin/customers/{customer_id}/documents/inspect-text")
async def api_admin_inspect_customer_document_text(
    customer_id: str,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    text: str = Form(...),
) -> dict:
    _admin_tenant_customer(db, customer_id)
    return inspect_text_content(db, customer_id, text)


@router.post("/api/admin/customers/{customer_id}/documents/merge-preview")
async def api_admin_merge_preview_customer_document(
    customer_id: str,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    target_document_id: str = Form(...),
    text: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    use_llm: str | None = Form(default=None),
) -> dict:
    _admin_tenant_customer(db, customer_id)
    combined, error = await _read_merge_source_text(prefix_text=text, file=file)
    if error is not None:
        return error
    assert combined is not None
    try:
        return merge_preview_for_documents(
            db,
            customer_id,
            target_document_id,
            combined,
            use_llm=parse_form_bool(use_llm),
        )
    except MergeError as exc:
        return _merge_error_response(exc)


@router.post("/api/admin/customers/{customer_id}/documents/{document_id}/merge")
async def api_admin_merge_customer_document(
    customer_id: str,
    document_id: str,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    blocks: str = Form(...),
    text: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    title: str | None = Form(default=None),
    merged_text: str | None = Form(default=None),
) -> dict:
    _admin_tenant_customer(db, customer_id)
    combined, error = await _read_merge_source_text(prefix_text=text, file=file)
    if error is not None:
        return error
    assert combined is not None
    try:
        parsed_blocks = json.loads(blocks)
    except json.JSONDecodeError:
        return JSONResponse({"error": "invalid_blocks"}, status_code=400)
    if not isinstance(parsed_blocks, list):
        return JSONResponse({"error": "invalid_blocks"}, status_code=400)
    try:
        result = apply_document_merge(
            db,
            customer_id,
            document_id,
            combined,
            parsed_blocks,
            title=title,
            merged_text_override=merged_text,
        )
    except MergeError as exc:
        return _merge_error_response(exc)
    return {"document": _document_payload(result["document"]), "stats": result["stats"]}


@router.post("/api/admin/customers/{customer_id}/documents")
async def api_admin_upload_customer_document(
    customer_id: str,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    title: str | None = Form(default=None),
    text: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    process_images: str | None = Form(default=None),
    transcribe_image_ids: str | None = Form(default=None),
    allow_duplicate: str | None = Form(default=None),
) -> dict:
    customer = _admin_tenant_customer(db, customer_id)
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
            process_images=parse_form_bool(process_images),
            transcribe_image_ids_raw=transcribe_image_ids,
            allow_duplicate=parse_form_bool(allow_duplicate),
        )
    except UploadError:
        raise
    return {"document": _document_payload(document)}


@router.get("/api/admin/customers/{customer_id}/documents/{document_id}")
def api_admin_get_customer_document(
    customer_id: str,
    document_id: str,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    customer = _admin_tenant_customer(db, customer_id)
    payload = _admin_document_detail(
        db,
        customer.id,
        document_id,
        assets_base_path=f"/api/admin/customers/{customer_id}/documents/{document_id}",
    )
    if payload is None:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return payload


@router.get("/api/admin/customers/{customer_id}/documents/{document_id}/images/{image_id}")
def api_admin_get_customer_document_image(
    customer_id: str,
    document_id: str,
    image_id: str,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Response:
    customer = _admin_tenant_customer(db, customer_id)
    document = get_document(db, customer.id, document_id)
    if document is None:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return _document_image_file_response(document, image_id)


@router.put("/api/admin/customers/{customer_id}/documents/{document_id}")
def api_admin_update_customer_document(
    customer_id: str,
    document_id: str,
    body: DocumentUpdateRequest,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    customer = _admin_tenant_customer(db, customer_id)
    try:
        result = update_document_content(
            db,
            customer.id,
            document_id,
            body.title,
            body.text,
        )
    except IngestionError as exc:
        if exc.code == "not_found":
            return JSONResponse({"error": "not_found"}, status_code=404)
        raise
    return {"document": _document_payload(result.document)}


@router.delete("/api/admin/customers/{customer_id}/documents/{document_id}")
def api_admin_delete_customer_document(
    customer_id: str,
    document_id: str,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    customer = _admin_tenant_customer(db, customer_id)
    deleted = delete_document(db, customer.id, document_id)
    if not deleted:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return JSONResponse({"deleted": True, "id": document_id})


@router.get("/api/admin/users")
def api_admin_list_users(
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    return {
        "users": list_admin_users(db),
        "customers": list_assignable_customers(db),
        "roles": list_admin_roles(db),
    }


@router.get("/api/admin/roles")
def api_admin_list_roles(
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    return {
        "roles": list_admin_roles(db),
        "customers": list_assignable_customers(db),
    }


@router.post("/api/admin/roles")
def api_admin_create_role(
    payload: AdminRoleCreateRequest,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    role = create_admin_role(
        db,
        payload.name,
        payload.customer_ids,
        is_admin=payload.is_admin,
        auto_add_new_customers=payload.auto_add_new_customers,
    )
    return {"role": role_to_dict(db, role)}


@router.patch("/api/admin/roles/{role_id}")
def api_admin_update_role(
    role_id: str,
    payload: AdminRoleUpdateRequest,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    role = update_admin_role(
        db,
        role_id,
        name=payload.name,
        customer_ids=payload.customer_ids,
        is_admin=payload.is_admin,
        auto_add_new_customers=payload.auto_add_new_customers,
    )
    return {"role": role_to_dict(db, role)}


@router.delete("/api/admin/roles/{role_id}")
def api_admin_delete_role(
    role_id: str,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    delete_admin_role(db, role_id)
    return {"deleted": True, "id": role_id}


@router.get("/api/admin/keys")
def api_admin_get_keys(
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    return get_keys_status(db)


@router.patch("/api/admin/keys/chat")
def api_admin_update_keys_chat(
    payload: AdminKeysChatUpdate,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    if payload.auth_mode is not None:
        update_secret(db, "chat_auth_mode", payload.auth_mode, _admin.email)
    if payload.api_key is not None:
        update_secret(db, "chat_api_key", payload.api_key, _admin.email)
    return get_keys_status(db)


@router.patch("/api/admin/keys/embedding")
def api_admin_update_keys_embedding(
    payload: AdminKeysEmbeddingUpdate,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    if payload.api_key is not None:
        update_secret(db, "embedding_api_key", payload.api_key, _admin.email)
    return get_keys_status(db)


@router.patch("/api/admin/keys/similarity")
def api_admin_update_keys_similarity(
    payload: AdminKeysSimilarityUpdate,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    if payload.mode is not None:
        update_secret(db, "similarity_mode", payload.mode, _admin.email)
    if payload.auth_mode is not None:
        update_secret(db, "similarity_auth_mode", payload.auth_mode, _admin.email)
    if payload.api_key is not None:
        update_secret(db, "similarity_api_key", payload.api_key, _admin.email)
    return get_keys_status(db)


@router.patch("/api/admin/keys/integration")
def api_admin_update_keys_integration(
    payload: AdminKeysIntegrationUpdate,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    if payload.api_key is not None:
        update_secret(db, "integration_api_token", payload.api_key, _admin.email)
    return get_keys_status(db)


@router.post("/api/admin/keys/oauth/start")
def api_admin_oauth_start(
    _admin: User = Depends(get_admin_user),
) -> dict:
    from app.oauth_device_flow import start_device_flow

    try:
        info = start_device_flow()
        return info
    except Exception as exc:
        raise SecretsAdminError("oauth_start_failed", status_code=502, detail=str(exc)) from exc


@router.post("/api/admin/keys/oauth/poll")
def api_admin_oauth_poll(
    device_auth_id: str,
    user_code: str,
    interval: int = 5,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    from app.oauth_device_flow import (
        exchange_and_save,
        get_oauth_target_path,
        poll_device_completion,
    )

    try:
        res = poll_device_completion(device_auth_id, user_code, interval, max_seconds=20)
        if res.get("status") != "complete":
            return {"status": res.get("status", "pending")}
        # complete: exchange + save file + set modes
        target = get_oauth_target_path()
        acc = exchange_and_save(
            res["authorization_code"],
            res["code_verifier"],
            target,
        )
        # ensure chat uses oauth
        update_secret(db, "chat_auth_mode", "chatgpt_oauth", _admin.email)
        # if similarity is in custom, also point it to oauth (reuses same file)
        if (get_effective_secret(db, "similarity_mode") or "same_as_chat") == "custom":
            update_secret(db, "similarity_auth_mode", "chatgpt_oauth", _admin.email)
        status = get_keys_status(db)
        status["oauth_account_id"] = acc.get("account_id")
        return {"status": "complete", "keys": status}
    except SecretsAdminError:
        raise
    except Exception as exc:
        raise SecretsAdminError("oauth_poll_failed", status_code=502, detail=str(exc)) from exc


@router.post("/api/admin/users")
def api_admin_create_user(
    payload: AdminUserCreateRequest,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    user = create_admin_user(
        db,
        payload.email,
        payload.password,
        payload.customer_ids,
        is_admin=payload.is_admin,
        role_ids=payload.role_ids,
    )
    return {"user": user_to_dict(db, user)}


@router.patch("/api/admin/users/{user_id}")
def api_admin_update_user(
    user_id: str,
    payload: AdminUserUpdateRequest,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    user = update_admin_user(
        db,
        user_id,
        actor_id=admin.id,
        email=payload.email,
        password=payload.password,
        customer_ids=payload.customer_ids,
        role_ids=payload.role_ids,
        is_admin=payload.is_admin,
        is_active=payload.is_active,
    )
    return {"user": user_to_dict(db, user)}


@router.delete("/api/admin/users/{user_id}")
def api_admin_delete_user(
    user_id: str,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    deactivate_admin_user(db, user_id, actor_id=admin.id)
    return {"deleted": True, "id": user_id}


@router.get("/api/admin/knowledge-sources")
def api_admin_list_knowledge_sources(
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    return {"sources": list_knowledge_sources(db)}


@router.post("/api/admin/knowledge-sources")
def api_admin_create_knowledge_source(
    payload: AdminKnowledgeSourceCreateRequest,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    source = create_knowledge_source(db, payload.name, payload.host_code)
    return {"source": source_to_dict(source)}


@router.patch("/api/admin/knowledge-sources/{source_id}")
def api_admin_update_knowledge_source(
    source_id: str,
    payload: AdminKnowledgeSourceUpdateRequest,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    source = update_knowledge_source(
        db,
        source_id,
        name=payload.name,
        active=payload.active,
    )
    return {"source": source_to_dict(source)}


@router.delete("/api/admin/knowledge-sources/{source_id}")
def api_admin_delete_knowledge_source(
    source_id: str,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    delete_knowledge_source(db, source_id)
    return {"deleted": True, "id": source_id}


@router.get("/api/tools/knowledge-center/contents")
def api_tools_knowledge_center_contents(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    status: str | None = "pending",
    source_id: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    contents, total = list_knowledge_contents(
        db,
        user,
        status=status,
        source_id=source_id,
        search=search,
        limit=limit,
        offset=offset,
    )
    return {
        "contents": contents,
        "total": total,
        "sources": list_knowledge_sources(db),
        "customers": list_adoptable_customers(db, user),
    }


@router.get("/api/tools/knowledge-center/contents/{content_id}")
def api_tools_knowledge_center_content_detail(
    content_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    row = get_knowledge_content_for_user(db, user, content_id)
    return {
        "content": content_to_dict(db, row),
        "customers": list_adoptable_customers(db, user),
    }


@router.post("/api/tools/knowledge-center/contents/{content_id}/adopt")
def api_tools_knowledge_center_adopt(
    content_id: str,
    payload: KnowledgeContentAdoptRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return adopt_knowledge_content(db, user, content_id, payload.customer_id)


@router.post("/api/tools/knowledge-center/contents/{content_id}/reject")
def api_tools_knowledge_center_reject(
    content_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return reject_knowledge_content(db, user, content_id)

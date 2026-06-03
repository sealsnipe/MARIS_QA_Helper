from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.agent import AgentError
from app.chats import ChatForbiddenError, ChatNotFoundError
from app.auth import ForbiddenError, NotAuthenticatedError
from app.config import get_settings
from app.db import SessionLocal, init_db
from app.ingestion import IngestionError
from app.routes import router
from app.tenant import CustomerNotFoundError, ForbiddenCustomerError
from app.customers import ensure_global_customer, CustomerAdminError
from app.users_admin import UserAdminError
from app.system_prompts import ensure_default_global_prompt
from app.upload import UploadError

settings = get_settings()
static_dir = Path(__file__).resolve().parent / "static"
static_dir.mkdir(exist_ok=True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    with SessionLocal() as db:
        ensure_global_customer(db)
        ensure_default_global_prompt(db)
    yield


app = FastAPI(title="SUP_QA_Helper", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
    session_cookie="session",
    max_age=60 * 60 * 24 * 7,
    same_site="lax",
    https_only=settings.SESSION_COOKIE_SECURE,
)
app.include_router(router)

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.exception_handler(NotAuthenticatedError)
async def not_authenticated_handler(request: Request, _exc: NotAuthenticatedError):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": "not_authenticated"}, status_code=401)
    return RedirectResponse(url="/login", status_code=302)


@app.exception_handler(ChatNotFoundError)
async def chat_not_found_handler(_request: Request, _exc: ChatNotFoundError):
    return JSONResponse({"error": "not_found"}, status_code=404)


@app.exception_handler(ChatForbiddenError)
async def chat_forbidden_handler(_request: Request, _exc: ChatForbiddenError):
    return JSONResponse({"error": "forbidden_customer"}, status_code=403)


@app.exception_handler(ForbiddenError)
async def forbidden_handler(_request: Request, _exc: ForbiddenError):
    return JSONResponse({"error": "forbidden"}, status_code=403)


@app.exception_handler(ForbiddenCustomerError)
async def forbidden_customer_handler(_request: Request, _exc: ForbiddenCustomerError):
    return JSONResponse({"error": "forbidden_customer"}, status_code=403)


@app.exception_handler(CustomerNotFoundError)
async def customer_not_found_handler(_request: Request, _exc: CustomerNotFoundError):
    return JSONResponse({"error": "not_found"}, status_code=404)


@app.exception_handler(CustomerAdminError)
async def customer_admin_error_handler(_request: Request, exc: CustomerAdminError):
    body: dict[str, str] = {"error": exc.code}
    if exc.detail:
        body["detail"] = exc.detail
    return JSONResponse(body, status_code=exc.status_code)


@app.exception_handler(UserAdminError)
async def user_admin_error_handler(_request: Request, exc: UserAdminError):
    body: dict[str, str] = {"error": exc.code}
    if exc.detail:
        body["detail"] = exc.detail
    return JSONResponse(body, status_code=exc.status_code)


@app.exception_handler(IngestionError)
async def ingestion_error_handler(_request: Request, exc: IngestionError):
    status_by_code = {
        "empty_text": 400,
        "invalid_title": 400,
        "embedding_failed": 502,
        "vector_store_failed": 502,
    }
    status_code = status_by_code.get(exc.code, 400)
    body: dict[str, str] = {"error": exc.code}
    if exc.detail:
        body["detail"] = exc.detail
    return JSONResponse(body, status_code=status_code)


@app.exception_handler(AgentError)
async def agent_error_handler(_request: Request, exc: AgentError):
    body: dict[str, str] = {"error": exc.code}
    if exc.detail:
        body["detail"] = exc.detail
    return JSONResponse(body, status_code=502)


@app.exception_handler(UploadError)
async def upload_error_handler(_request: Request, exc: UploadError):
    status_by_code = {
        "unsupported_file_type": 400,
        "empty_text": 400,
        "file_too_large": 413,
        "extraction_failed": 422,
    }
    status_code = status_by_code.get(exc.code, 400)
    body: dict[str, str] = {"error": exc.code}
    if exc.detail:
        body["detail"] = exc.detail
    return JSONResponse(body, status_code=status_code)

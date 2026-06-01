from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.auth import NotAuthenticatedError
from app.config import get_settings
from app.db import init_db
from app.routes import router
from app.tenant import CustomerNotFoundError, ForbiddenCustomerError

settings = get_settings()
static_dir = Path(__file__).resolve().parent / "static"
static_dir.mkdir(exist_ok=True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="SUP_QA_Helper", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
    session_cookie="session",
    max_age=60 * 60 * 24 * 7,
    same_site="lax",
    https_only=False,
)
app.include_router(router)

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.exception_handler(NotAuthenticatedError)
async def not_authenticated_handler(request: Request, _exc: NotAuthenticatedError):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": "not_authenticated"}, status_code=401)
    return RedirectResponse(url="/login", status_code=302)


@app.exception_handler(ForbiddenCustomerError)
async def forbidden_customer_handler(_request: Request, _exc: ForbiddenCustomerError):
    return JSONResponse({"error": "forbidden_customer"}, status_code=403)


@app.exception_handler(CustomerNotFoundError)
async def customer_not_found_handler(_request: Request, _exc: CustomerNotFoundError):
    return JSONResponse({"error": "not_found"}, status_code=404)

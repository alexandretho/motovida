import json
import logging
import sys
from ipaddress import ip_address, ip_network
from secrets import token_urlsafe
from time import perf_counter
from urllib.parse import parse_qs
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import models  # noqa: F401  (registra os modelos no metadata)
from . import ratelimit
from .config import (
    ALLOWED_HOSTS,
    MAX_FORM_BODY_BYTES,
    RUNTIME_CONFIG_WARNINGS,
    SECRET_KEY,
    SESSION_COOKIE_MAX_AGE_SECONDS,
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_SAME_SITE,
    SESSION_COOKIE_SECURE,
)
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine, get_db, wait_for_db
from .deps import base_ctx, is_valid_csrf_token
from .routers import admin, affiliate, auth, public
from .scheduling import ensure_lgpd_consent_ip_column, ensure_scheduled_at_column
from .seeds import run_seeds
from .security import is_sensitive_scanner_path

app = FastAPI(title="Sistema Nacional de Cadastro e Atendimento – Instituto MotoVida Guilherme França")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS, www_redirect=False)
http_logger = logging.getLogger("app.http")
http_logger.setLevel(logging.INFO)
if not http_logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    http_logger.addHandler(handler)
config_logger = logging.getLogger("app.config")

_error_templates = Jinja2Templates(directory="app/templates")


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404 and "text/html" in request.headers.get("accept", ""):
        return _error_templates.TemplateResponse(request, "public/404.html", base_ctx(request, None), status_code=404)
    return PlainTextResponse(str(exc.detail), status_code=exc.status_code, headers=getattr(exc, "headers", None))


app.mount("/static", StaticFiles(directory="app/static"), name="static")

SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), geolocation=(), microphone=()",
    "Strict-Transport-Security": "max-age=31536000",
    "Cross-Origin-Opener-Policy": "same-origin",
    "X-Permitted-Cross-Domain-Policies": "none",
}

NO_STORE_PREFIXES = ("/admin", "/afiliado", "/login", "/logout", "/recuperar-senha")
NO_INDEX_PREFIXES = (*NO_STORE_PREFIXES, "/cadastro")
SESSION_VARY_PREFIXES = (*NO_INDEX_PREFIXES, "/contato")
BLOCKED_HTTP_METHODS = {"TRACE", "TRACK", "CONNECT"}
REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_MAX_LENGTH = 64
REQUEST_ID_ALLOWED_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")


def get_request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        return request_id

    candidate = request.headers.get(REQUEST_ID_HEADER, "").strip()
    if (
        candidate
        and len(candidate) <= REQUEST_ID_MAX_LENGTH
        and all(char in REQUEST_ID_ALLOWED_CHARS for char in candidate)
    ):
        request.state.request_id = candidate
    else:
        request.state.request_id = uuid4().hex
    return request.state.request_id


def anonymize_ip_for_log(value: str) -> str:
    try:
        ip = ip_address(value)
    except ValueError:
        return "unknown"

    prefix = 24 if ip.version == 4 else 48
    return str(ip_network(f"{ip}/{prefix}", strict=False).network_address)


@app.middleware("http")
async def log_http_requests(request: Request, call_next):
    request_id = get_request_id(request)
    if request.url.path in ("/healthz", "/readyz"):
        return await call_next(request)

    started_at = perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        duration_ms = round((perf_counter() - started_at) * 1000, 2)
        http_logger.info(
            json.dumps(
                {
                    "event": "http_request",
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "client_ip": anonymize_ip_for_log(ratelimit.client_ip(request)),
                    "request_id": request_id,
                },
                separators=(",", ":"),
            )
        )


def build_content_security_policy(nonce: str) -> str:
    return "; ".join([
        "default-src 'self'",
        "base-uri 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "form-action 'self'",
        "img-src 'self' data: https://www.google-analytics.com https://www.googletagmanager.com",
        "style-src 'self' 'unsafe-inline'",
        f"script-src 'self' 'nonce-{nonce}' https://www.googletagmanager.com",
        "connect-src 'self' https://www.google-analytics.com https://region1.google-analytics.com",
        "upgrade-insecure-requests",
    ])


def apply_security_headers(response, path: str = ""):
    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    if path.startswith(NO_STORE_PREFIXES):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    if path.startswith(SESSION_VARY_PREFIXES):
        vary = {value.strip() for value in response.headers.get("Vary", "").split(",") if value.strip()}
        vary.add("Cookie")
        response.headers["Vary"] = ", ".join(sorted(vary))
    if path.startswith(NO_INDEX_PREFIXES) or is_sensitive_scanner_path(path):
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


def request_body_too_large(request: Request, body: bytes | None = None) -> bool:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_FORM_BODY_BYTES:
                return True
        except ValueError:
            return True
    return body is not None and len(body) > MAX_FORM_BODY_BYTES


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    request_id = get_request_id(request)
    csp_nonce = token_urlsafe(16)
    request.state.csp_nonce = csp_nonce

    if request.method.upper() in BLOCKED_HTTP_METHODS:
        response = PlainTextResponse("", status_code=405)
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers.setdefault("Content-Security-Policy", build_content_security_policy(csp_nonce))
        return apply_security_headers(response, request.url.path)

    if is_sensitive_scanner_path(request.url.path):
        response = PlainTextResponse("Not Found", status_code=404)
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers.setdefault("Content-Security-Policy", build_content_security_policy(csp_nonce))
        return apply_security_headers(response, request.url.path)

    if request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
        if request_body_too_large(request):
            response = PlainTextResponse("Payload muito grande.", status_code=413)
            response.headers[REQUEST_ID_HEADER] = request_id
            response.headers.setdefault("Content-Security-Policy", build_content_security_policy(csp_nonce))
            return apply_security_headers(response, request.url.path)

        body = await request.body()
        if request_body_too_large(request, body):
            response = PlainTextResponse("Payload muito grande.", status_code=413)
            response.headers[REQUEST_ID_HEADER] = request_id
            response.headers.setdefault("Content-Security-Policy", build_content_security_policy(csp_nonce))
            return apply_security_headers(response, request.url.path)

        parsed = parse_qs(body.decode("utf-8", "ignore"), keep_blank_values=True)
        csrf_token = parsed.get("csrf_token", [None])[0]
        if not isinstance(csrf_token, str) or not is_valid_csrf_token(request, csrf_token):
            response = PlainTextResponse("Token CSRF inválido ou ausente.", status_code=403)
            response.headers[REQUEST_ID_HEADER] = request_id
            response.headers.setdefault("Content-Security-Policy", build_content_security_policy(csp_nonce))
            return apply_security_headers(response, request.url.path)

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        request._receive = receive

    response = await call_next(request)
    response.headers[REQUEST_ID_HEADER] = request_id
    response.headers.setdefault("Content-Security-Policy", build_content_security_policy(csp_nonce))
    return apply_security_headers(response, request.url.path)


app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie=SESSION_COOKIE_NAME,
    max_age=SESSION_COOKIE_MAX_AGE_SECONDS,
    same_site=SESSION_COOKIE_SAME_SITE,
    https_only=SESSION_COOKIE_SECURE,
)


app.include_router(public.router)
app.include_router(auth.router)
app.include_router(affiliate.router)
app.include_router(admin.router)


@app.get("/healthz", include_in_schema=False)
def healthz():
    return PlainTextResponse("ok")


@app.head("/healthz", include_in_schema=False)
def healthz_head():
    return PlainTextResponse("")


@app.get("/readyz", include_in_schema=False)
def readyz(db: Session = Depends(get_db)):
    headers = {"Cache-Control": "no-store"}
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse({"status": "unavailable"}, status_code=503, headers=headers)
    return JSONResponse({"status": "ready"}, headers=headers)


@app.head("/readyz", include_in_schema=False)
def readyz_head(db: Session = Depends(get_db)):
    headers = {"Cache-Control": "no-store"}
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        return Response(status_code=503, headers=headers)
    return Response(headers=headers)


@app.on_event("startup")
def startup():
    for warning in RUNTIME_CONFIG_WARNINGS:
        config_logger.warning("runtime_config_warning: %s", warning)
    wait_for_db()
    Base.metadata.create_all(bind=engine)
    ensure_scheduled_at_column(engine)
    ensure_lgpd_consent_ip_column(engine)
    db = SessionLocal()
    try:
        run_seeds(db)
    finally:
        db.close()

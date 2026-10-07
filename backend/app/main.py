import json
import logging
import sys
from secrets import token_urlsafe
from time import perf_counter
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from . import models  # noqa: F401  (registra os modelos no metadata)
from . import ratelimit
from .config import SECRET_KEY, SESSION_COOKIE_SECURE
from .database import Base, SessionLocal, engine, wait_for_db
from .deps import is_valid_csrf_token
from .routers import admin, affiliate, auth, public
from .scheduling import ensure_scheduled_at_column
from .seeds import run_seeds
from .security import is_sensitive_scanner_path

app = FastAPI(title="Sistema Nacional de Cadastro e Atendimento – Instituto MotoVida Guilherme França")
http_logger = logging.getLogger("app.http")
http_logger.setLevel(logging.INFO)
if not http_logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    http_logger.addHandler(handler)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), geolocation=(), microphone=()",
    "Strict-Transport-Security": "max-age=31536000",
}

NO_STORE_PREFIXES = ("/admin", "/afiliado", "/login", "/logout", "/recuperar-senha")
NO_INDEX_PREFIXES = (*NO_STORE_PREFIXES, "/cadastro")


@app.middleware("http")
async def log_http_requests(request: Request, call_next):
    if request.url.path == "/healthz":
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
                    "client_ip": ratelimit.client_ip(request),
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
    if path.startswith(NO_INDEX_PREFIXES) or is_sensitive_scanner_path(path):
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    csp_nonce = token_urlsafe(16)
    request.state.csp_nonce = csp_nonce

    if is_sensitive_scanner_path(request.url.path):
        response = PlainTextResponse("Not Found", status_code=404)
        response.headers.setdefault("Content-Security-Policy", build_content_security_policy(csp_nonce))
        return apply_security_headers(response, request.url.path)

    if request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
        body = await request.body()
        parsed = parse_qs(body.decode("utf-8", "ignore"), keep_blank_values=True)
        csrf_token = parsed.get("csrf_token", [None])[0]
        if not isinstance(csrf_token, str) or not is_valid_csrf_token(request, csrf_token):
            response = PlainTextResponse("Token CSRF inválido ou ausente.", status_code=403)
            response.headers.setdefault("Content-Security-Policy", build_content_security_policy(csp_nonce))
            return apply_security_headers(response, request.url.path)

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        request._receive = receive

    response = await call_next(request)
    response.headers.setdefault("Content-Security-Policy", build_content_security_policy(csp_nonce))
    return apply_security_headers(response, request.url.path)


app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    max_age=60 * 60 * 8,
    same_site="lax",
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


@app.on_event("startup")
def startup():
    wait_for_db()
    Base.metadata.create_all(bind=engine)
    ensure_scheduled_at_column(engine)
    db = SessionLocal()
    try:
        run_seeds(db)
    finally:
        db.close()

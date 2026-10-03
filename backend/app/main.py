from secrets import token_urlsafe
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from . import models  # noqa: F401  (registra os modelos no metadata)
from .config import SECRET_KEY
from .database import Base, SessionLocal, engine, wait_for_db
from .deps import is_valid_csrf_token
from .routers import admin, affiliate, auth, public
from .seeds import run_seeds
from .security import is_sensitive_scanner_path

app = FastAPI(title="Sistema Nacional de Cadastro e Atendimento – Instituto MotoVida Guilherme França")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), geolocation=(), microphone=()",
}


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


def apply_security_headers(response):
    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    return response


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    csp_nonce = token_urlsafe(16)
    request.state.csp_nonce = csp_nonce

    if is_sensitive_scanner_path(request.url.path):
        response = PlainTextResponse("Not Found", status_code=404)
        response.headers.setdefault("Content-Security-Policy", build_content_security_policy(csp_nonce))
        return apply_security_headers(response)

    if request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
        body = await request.body()
        parsed = parse_qs(body.decode("utf-8", "ignore"), keep_blank_values=True)
        csrf_token = parsed.get("csrf_token", [None])[0]
        if not isinstance(csrf_token, str) or not is_valid_csrf_token(request, csrf_token):
            response = PlainTextResponse("Token CSRF inválido ou ausente.", status_code=403)
            response.headers.setdefault("Content-Security-Policy", build_content_security_policy(csp_nonce))
            return apply_security_headers(response)

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        request._receive = receive

    response = await call_next(request)
    response.headers.setdefault("Content-Security-Policy", build_content_security_policy(csp_nonce))
    return apply_security_headers(response)


app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=60 * 60 * 8, same_site="lax")


app.include_router(public.router)
app.include_router(auth.router)
app.include_router(affiliate.router)
app.include_router(admin.router)


@app.on_event("startup")
def startup():
    wait_for_db()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        run_seeds(db)
    finally:
        db.close()

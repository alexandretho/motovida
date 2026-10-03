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

app = FastAPI(title="Sistema Nacional de Cadastro e Atendimento – Instituto MotoVida Guilherme França")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), geolocation=(), microphone=()",
}


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    if request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
        body = await request.body()
        parsed = parse_qs(body.decode("utf-8", "ignore"), keep_blank_values=True)
        csrf_token = parsed.get("csrf_token", [None])[0]
        if not isinstance(csrf_token, str) or not is_valid_csrf_token(request, csrf_token):
            return PlainTextResponse("Token CSRF inválido ou ausente.", status_code=403)

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        request._receive = receive

    response = await call_next(request)
    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    return response


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

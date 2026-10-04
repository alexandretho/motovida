from dataclasses import dataclass
from threading import Lock
from time import monotonic

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import base_ctx, flash, get_current_user
from ..security import verify_password
from ..validators import sanitize

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

LOGIN_FAILURE_LIMIT = 5
LOGIN_FAILURE_WINDOW_SECONDS = 5 * 60
LOGIN_RATE_LIMIT_MESSAGE = "Muitas tentativas inválidas. Aguarde alguns minutos antes de tentar novamente."


@dataclass
class LoginFailureWindow:
    count: int
    started_at: float


_login_failures: dict[tuple[str, str], LoginFailureWindow] = {}
_login_failures_lock = Lock()


def _login_rate_limit_key(request: Request, email: str) -> tuple[str, str]:
    ip = request.client.host if request.client else "unknown"
    return ip, email.strip().lower()


def _prune_login_failures(now: float):
    expired_keys = [
        key for key, window in _login_failures.items()
        if now - window.started_at >= LOGIN_FAILURE_WINDOW_SECONDS
    ]
    for key in expired_keys:
        _login_failures.pop(key, None)


def is_login_rate_limited(key: tuple[str, str], now: float | None = None) -> bool:
    now = monotonic() if now is None else now
    with _login_failures_lock:
        _prune_login_failures(now)
        window = _login_failures.get(key)
        return bool(window and window.count >= LOGIN_FAILURE_LIMIT)


def record_failed_login(key: tuple[str, str], now: float | None = None) -> bool:
    now = monotonic() if now is None else now
    with _login_failures_lock:
        _prune_login_failures(now)
        window = _login_failures.get(key)
        if window:
            window.count += 1
        else:
            window = LoginFailureWindow(count=1, started_at=now)
            _login_failures[key] = window
        return window.count >= LOGIN_FAILURE_LIMIT


def reset_login_rate_limit(key: tuple[str, str]):
    with _login_failures_lock:
        _login_failures.pop(key, None)


@router.get("/login")
def login_form(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user:
        return RedirectResponse("/admin" if user.role == "admin" else "/afiliado", status_code=303)
    return templates.TemplateResponse("public/login.html", base_ctx(request, None))


@router.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...),
          db: Session = Depends(get_db)):
    email = sanitize(email, 180)
    rate_limit_key = _login_rate_limit_key(request, email)
    if is_login_rate_limited(rate_limit_key):
        flash(request, LOGIN_RATE_LIMIT_MESSAGE, "error")
        return RedirectResponse("/login", status_code=303)

    user = db.query(models.User).filter_by(email=email).first()
    if not user or not verify_password(password, user.password_hash):
        message = LOGIN_RATE_LIMIT_MESSAGE if record_failed_login(rate_limit_key) else "E-mail ou senha incorretos."
        flash(request, message, "error")
        return RedirectResponse("/login", status_code=303)
    reset_login_rate_limit(rate_limit_key)
    request.session["user_id"] = user.id
    return RedirectResponse("/admin" if user.role == "admin" else "/afiliado", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)

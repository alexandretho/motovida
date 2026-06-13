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
    user = db.query(models.User).filter_by(email=email).first()
    if not user or not verify_password(password, user.password_hash):
        flash(request, "E-mail ou senha incorretos.", "error")
        return RedirectResponse("/login", status_code=303)
    request.session["user_id"] = user.id
    return RedirectResponse("/admin" if user.role == "admin" else "/afiliado", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)

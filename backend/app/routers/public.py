from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..config import POLICY_VERSION
from ..database import get_db
from ..deps import base_ctx, flash, get_current_user
from ..security import hash_password
from ..validators import (clean_cpf, is_valid_cpf, is_valid_email, is_valid_uf, sanitize)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

BENEFITS = [
    ("⚖️", "Apoio Jurídico", "Orientação em acidentes de trânsito, dúvidas trabalhistas e previdenciárias."),
    ("💙", "Apoio Psicológico", "Acolhimento emocional para vítimas de acidentes e seus familiares."),
    ("📚", "Cursos e Capacitações", "Direção defensiva, primeiros socorros, segurança e desenvolvimento profissional."),
    ("📋", "Auxílio MEI", "Passo a passo para abrir, regularizar e manter o seu MEI em dia."),
    ("🤝", "Rede de Parceiros", "Descontos em oficinas, peças, clínicas, farmácias, combustível e mais."),
    ("🆘", "Canal de Ajuda", "Abra solicitações de apoio social, jurídico, psicológico ou administrativo."),
]


@router.get("/")
def index(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    partners = db.query(models.Partner).filter_by(active=True).limit(6).all()
    return templates.TemplateResponse("public/index.html",
        base_ctx(request, user, benefits=BENEFITS, partners=partners))


@router.get("/parceiros")
def partners_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    partners = db.query(models.Partner).filter_by(active=True).order_by(models.Partner.category).all()
    return templates.TemplateResponse("public/parceiros.html", base_ctx(request, user, partners=partners))


@router.get("/contato")
def contact(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("public/contato.html", base_ctx(request, get_current_user(request, db)))


@router.get("/privacidade")
def privacy(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("public/privacidade.html",
        base_ctx(request, get_current_user(request, db), version=POLICY_VERSION))


@router.get("/cadastro")
def register_form(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("public/cadastro.html",
        base_ctx(request, get_current_user(request, db), form={}, errors=[]))


@router.post("/cadastro")
def register(
    request: Request,
    full_name: str = Form(...), cpf: str = Form(...), phone: str = Form(...),
    whatsapp: str = Form(...), email: str = Form(...), city: str = Form(...),
    state: str = Form(...), profession: str = Form(...), mei_status: str = Form(...),
    support_needs: str = Form(""), password: str = Form(...),
    lgpd_accept: str = Form(None), db: Session = Depends(get_db),
):
    form = {k: sanitize(v, 300) for k, v in {
        "full_name": full_name, "cpf": cpf, "phone": phone, "whatsapp": whatsapp,
        "email": email, "city": city, "state": state.upper(), "profession": profession,
        "mei_status": mei_status}.items()}
    form["support_needs"] = sanitize(support_needs)

    errors = []
    if len(form["full_name"]) < 5:
        errors.append("Informe o nome completo.")
    if not is_valid_cpf(form["cpf"]):
        errors.append("CPF inválido. Verifique os dígitos informados.")
    if not is_valid_email(form["email"]):
        errors.append("E-mail inválido.")
    if not is_valid_uf(form["state"]):
        errors.append("Selecione um estado (UF) válido.")
    if form["profession"] not in models.PROFESSIONS:
        errors.append("Selecione uma profissão válida.")
    if form["mei_status"] not in models.MEI_STATUSES:
        errors.append("Selecione a situação do MEI.")
    if len(password) < 6:
        errors.append("A senha precisa ter pelo menos 6 caracteres.")
    if lgpd_accept != "on":
        errors.append("É necessário aceitar a Política de Privacidade (LGPD) para se cadastrar.")

    cpf_clean = clean_cpf(form["cpf"])
    if not errors:
        if db.query(models.User).filter_by(email=form["email"]).first():
            errors.append("Já existe um cadastro com este e-mail.")
        if db.query(models.Affiliate).filter_by(cpf=cpf_clean).first():
            errors.append("Já existe um cadastro com este CPF.")

    if errors:
        return templates.TemplateResponse("public/cadastro.html",
            base_ctx(request, None, form=form, errors=errors), status_code=400)

    user = models.User(email=form["email"], password_hash=hash_password(password), role="affiliate")
    db.add(user)
    db.flush()
    affiliate = models.Affiliate(
        user_id=user.id, full_name=form["full_name"], cpf=cpf_clean, phone=form["phone"],
        whatsapp=form["whatsapp"], email=form["email"], city=form["city"], state=form["state"],
        profession=form["profession"], mei_status=form["mei_status"], support_needs=form["support_needs"],
    )
    db.add(affiliate)
    db.flush()
    db.add(models.LgpdConsent(affiliate_id=affiliate.id, accepted=True, policy_version=POLICY_VERSION))
    db.commit()

    flash(request, "Cadastro realizado com sucesso! Entre com seu e-mail e senha.")
    return RedirectResponse("/login", status_code=303)

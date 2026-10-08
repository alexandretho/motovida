from datetime import datetime
import csv
from io import StringIO
from math import ceil
from typing import Optional, cast
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..scheduling import parse_schedule
from ..database import get_db
from ..deps import base_ctx, flash, get_current_user
from ..security import hash_password, verify_password
from ..support_history import add_specialized_history, build_specialized_history_map
from ..validators import is_valid_email, sanitize

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/templates")
ADMIN_PAGE_SIZE = 20

KIND_MODELS = {"juridico": models.LegalSupport, "psicologico": models.PsychologicalSupport,
               "mei": models.MeiSupport}


def build_pagination(total: int, page: int, per_page: int = ADMIN_PAGE_SIZE) -> dict:
    pages = max(1, ceil(total / per_page))
    current = min(max(page, 1), pages)
    return {
        "page": current,
        "per_page": per_page,
        "total": total,
        "pages": pages,
        "has_prev": current > 1,
        "has_next": current < pages,
        "prev_page": current - 1,
        "next_page": current + 1,
        "start": 0 if total == 0 else (current - 1) * per_page + 1,
        "end": min(current * per_page, total),
    }


def paginate_query(query, page: int, per_page: int = ADMIN_PAGE_SIZE):
    total = query.count()
    pagination = build_pagination(total, page, per_page)
    items = query.offset((pagination["page"] - 1) * per_page).limit(per_page).all()
    return items, pagination


def with_page_urls(pagination: dict, path: str, **params) -> dict:
    clean_params = {key: value for key, value in params.items() if value not in (None, "")}

    def page_url(page_number: int) -> str:
        query = urlencode({**clean_params, "page": page_number})
        return f"{path}?{query}"

    pagination["prev_url"] = page_url(pagination["prev_page"])
    pagination["next_url"] = page_url(pagination["next_page"])
    return pagination


def filter_affiliates_query(query, estado: str = "", cidade: str = "", profissao: str = ""):
    if estado:
        query = query.filter(models.Affiliate.state == estado.upper())
    if cidade:
        query = query.filter(models.Affiliate.city.ilike(f"%{sanitize(cidade, 120)}%"))
    if profissao in models.PROFESSIONS:
        query = query.filter(models.Affiliate.profession == profissao)
    return query


def latest_lgpd_consents_by_affiliate(db: Session, affiliate_ids: list[int]) -> dict[int, models.LgpdConsent]:
    """Retorna o aceite LGPD mais recente por afiliado para relatórios administrativos."""
    if not affiliate_ids:
        return {}

    consents = db.query(models.LgpdConsent)\
        .filter(models.LgpdConsent.affiliate_id.in_(affiliate_ids))\
        .order_by(models.LgpdConsent.affiliate_id.asc(), models.LgpdConsent.accepted_at.desc())\
        .all()
    latest: dict[int, models.LgpdConsent] = {}
    for consent in consents:
        latest.setdefault(cast(int, consent.affiliate_id), consent)
    return latest


def filtered_url(path: str, **params) -> str:
    clean_params = {key: value for key, value in params.items() if value not in (None, "")}
    query = urlencode(clean_params)
    return f"{path}?{query}" if query else path


def require_admin(request: Request, db: Session):
    user = get_current_user(request, db)
    return user if user and user.role == "admin" else None


def guard(user):
    return RedirectResponse("/login", status_code=303) if user is None else None


def validate_admin_password_change(current_password: str, new_password: str, confirm_password: str,
                                   stored_hash: str) -> list[str]:
    errors = []
    if not verify_password(current_password, stored_hash):
        errors.append("Senha atual incorreta.")
    if len(new_password) < 8:
        errors.append("A nova senha deve ter pelo menos 8 caracteres.")
    if new_password != confirm_password:
        errors.append("A confirmação da nova senha não confere.")
    if current_password and new_password and current_password == new_password:
        errors.append("Escolha uma senha diferente da atual.")
    return errors


def validate_affiliate_password_reset(new_password: str, confirm_password: str) -> list[str]:
    errors = []
    if len(new_password) < 8:
        errors.append("A nova senha deve ter pelo menos 8 caracteres.")
    if new_password != confirm_password:
        errors.append("A confirmação da nova senha não confere.")
    return errors


def validate_new_admin(email: str, password: str, confirm_password: str, email_exists: bool) -> list[str]:
    errors = []
    if not is_valid_email(email):
        errors.append("E-mail inválido.")
    elif email_exists:
        errors.append("Já existe um usuário com este e-mail.")
    if len(password) < 8:
        errors.append("A senha deve ter pelo menos 8 caracteres.")
    if password != confirm_password:
        errors.append("A confirmação da senha não confere.")
    return errors


@router.get("")
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    total_affiliates = db.query(models.Affiliate).count()
    by_state = db.query(models.Affiliate.state, func.count()).group_by(models.Affiliate.state)\
        .order_by(func.count().desc()).all()
    by_city = db.query(models.Affiliate.city, models.Affiliate.state, func.count())\
        .group_by(models.Affiliate.city, models.Affiliate.state).order_by(func.count().desc()).limit(10).all()
    by_type = db.query(models.SupportRequest.type, func.count())\
        .group_by(models.SupportRequest.type).order_by(func.count().desc()).all()
    by_status = db.query(models.SupportRequest.status, func.count())\
        .group_by(models.SupportRequest.status).all()
    by_profession = db.query(models.Affiliate.profession, func.count())\
        .group_by(models.Affiliate.profession).order_by(func.count().desc()).all()
    by_mei = db.query(models.Affiliate.mei_status, func.count())\
        .group_by(models.Affiliate.mei_status).order_by(func.count().desc()).all()
    top_courses = db.query(models.Course.title, func.count(models.CourseEnrollment.id))\
        .outerjoin(models.CourseEnrollment).group_by(models.Course.id)\
        .order_by(func.count(models.CourseEnrollment.id).desc()).limit(5).all()
    open_requests = db.query(models.SupportRequest)\
        .filter(models.SupportRequest.status.in_(["aberta", "em_analise"]))\
        .order_by(models.SupportRequest.created_at.desc()).limit(8).all()
    return templates.TemplateResponse(request, "admin/dashboard.html", base_ctx(
        request, user, total_affiliates=total_affiliates, by_state=by_state, by_city=by_city,
        by_type=by_type, by_status=by_status, by_profession=by_profession, by_mei=by_mei,
        top_courses=top_courses, open_requests=open_requests))


@router.get("/senha")
def password_form(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    return templates.TemplateResponse(request, "admin/senha.html", base_ctx(request, user))


@router.post("/senha")
def password_update(request: Request, current_password: str = Form(...), new_password: str = Form(...),
                    confirm_password: str = Form(...), db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r

    errors = validate_admin_password_change(current_password, new_password, confirm_password,
                                            user.password_hash)
    if errors:
        flash(request, " ".join(errors), "error")
        return RedirectResponse("/admin/senha", status_code=303)

    user.password_hash = hash_password(new_password)
    db.commit()
    flash(request, "Senha administrativa atualizada com sucesso.")
    return RedirectResponse("/admin", status_code=303)


@router.get("/afiliados")
def affiliates(request: Request, estado: str = "", cidade: str = "", profissao: str = "", page: int = 1,
               db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    q = filter_affiliates_query(db.query(models.Affiliate), estado, cidade, profissao)
    items, pagination = paginate_query(q.order_by(models.Affiliate.created_at.desc()), page)
    pagination = with_page_urls(pagination, "/admin/afiliados", estado=estado.upper(), cidade=cidade,
                                profissao=profissao)
    states = [s[0] for s in db.query(models.Affiliate.state).distinct().order_by(models.Affiliate.state)]
    export_url = filtered_url("/admin/afiliados.csv", estado=estado.upper(), cidade=cidade, profissao=profissao)
    return templates.TemplateResponse(request, "admin/afiliados.html", base_ctx(
        request, user, items=items, states=states,
        f_estado=estado.upper(), f_cidade=cidade, f_profissao=profissao, pagination=pagination,
        export_url=export_url))


@router.get("/afiliados.csv")
def affiliates_csv(request: Request, estado: str = "", cidade: str = "", profissao: str = "",
                   db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r

    rows = filter_affiliates_query(db.query(models.Affiliate), estado, cidade, profissao)\
        .order_by(models.Affiliate.created_at.desc()).all()
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([
        "id", "nome", "cpf", "email", "telefone", "whatsapp", "cidade", "estado",
        "profissao", "mei", "necessidades_apoio", "lgpd_aceite", "lgpd_versao", "lgpd_aceito_em",
        "cadastrado_em",
    ])
    consent_by_affiliate = latest_lgpd_consents_by_affiliate(db, [cast(int, affiliate.id) for affiliate in rows])
    for affiliate in rows:
        consent = consent_by_affiliate.get(cast(int, affiliate.id))
        writer.writerow([
            affiliate.id,
            affiliate.full_name,
            affiliate.cpf,
            affiliate.email,
            affiliate.phone,
            affiliate.whatsapp,
            affiliate.city,
            affiliate.state,
            affiliate.profession,
            affiliate.mei_status,
            affiliate.support_needs or "",
            "sim" if consent is not None and bool(consent.accepted) else "nao",
            consent.policy_version if consent else "",
            consent.accepted_at.isoformat() if consent else "",
            affiliate.created_at.isoformat(),
        ])
    return Response(
        output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="afiliados.csv"'},
    )


@router.get("/afiliados/{aff_id}")
def affiliate_detail(request: Request, aff_id: int, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    aff = db.query(models.Affiliate).filter_by(id=aff_id).first()
    if not aff:
        return RedirectResponse("/admin/afiliados", status_code=303)
    consent = db.query(models.LgpdConsent).filter_by(affiliate_id=aff.id)\
        .order_by(models.LgpdConsent.accepted_at.desc()).first()
    attendances = db.query(models.Attendance).filter_by(affiliate_id=aff.id)\
        .order_by(models.Attendance.created_at.desc()).all()
    return templates.TemplateResponse(request, "admin/afiliado_detalhe.html", base_ctx(
        request, user, aff=aff, consent=consent, attendances=attendances))


@router.post("/afiliados/{aff_id}/atendimento")
def add_attendance(request: Request, aff_id: int, notes: str = Form(...),
                   db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    if sanitize(notes):
        db.add(models.Attendance(affiliate_id=aff_id, admin_id=user.id, notes=sanitize(notes)))
        db.commit()
        flash(request, "Atendimento registrado.")
    return RedirectResponse(f"/admin/afiliados/{aff_id}", status_code=303)


@router.post("/afiliados/{aff_id}/senha")
def affiliate_password_reset(request: Request, aff_id: int, new_password: str = Form(...),
                             confirm_password: str = Form(...), db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r

    affiliate = db.query(models.Affiliate).filter_by(id=aff_id).first()
    if not affiliate:
        flash(request, "Afiliado não encontrado.", "error")
        return RedirectResponse("/admin/afiliados", status_code=303)

    errors = validate_affiliate_password_reset(new_password, confirm_password)
    if errors:
        flash(request, " ".join(errors), "error")
        return RedirectResponse(f"/admin/afiliados/{aff_id}", status_code=303)

    if not affiliate.user:
        flash(request, "Usuário de acesso do afiliado não encontrado.", "error")
        return RedirectResponse(f"/admin/afiliados/{aff_id}", status_code=303)

    affiliate.user.password_hash = hash_password(new_password)
    db.add(models.Attendance(
        affiliate_id=affiliate.id,
        admin_id=user.id,
        notes="Senha de acesso redefinida pelo painel administrativo.",
    ))
    db.commit()
    flash(request, "Senha do afiliado redefinida com sucesso.")
    return RedirectResponse(f"/admin/afiliados/{aff_id}", status_code=303)


@router.get("/solicitacoes")
def requests_list(request: Request, tipo: str = "", status: str = "", page: int = 1,
                  db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    q = db.query(models.SupportRequest)
    if tipo in models.REQUEST_TYPES:
        q = q.filter(models.SupportRequest.type == tipo)
    if status in models.STATUSES:
        q = q.filter(models.SupportRequest.status == status)
    items, pagination = paginate_query(q.order_by(models.SupportRequest.created_at.desc()), page)
    pagination = with_page_urls(pagination, "/admin/solicitacoes", tipo=tipo, status=status)
    return templates.TemplateResponse(request, "admin/solicitacoes.html", base_ctx(
        request, user, items=items, f_tipo=tipo, f_status=status, pagination=pagination))


@router.get("/solicitacoes/{req_id}")
def request_detail(request: Request, req_id: int, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    item = db.query(models.SupportRequest).filter_by(id=req_id).first()
    if not item:
        return RedirectResponse("/admin/solicitacoes", status_code=303)
    return templates.TemplateResponse(request, "admin/solicitacao_detalhe.html", base_ctx(request, user, item=item))


@router.post("/solicitacoes/{req_id}/status")
def request_status(request: Request, req_id: int, status: str = Form(...),
                   note: str = Form(""), db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    item = db.query(models.SupportRequest).filter_by(id=req_id).first()
    if item and status in models.STATUSES:
        db.add(models.RequestHistory(request_id=item.id, old_status=item.status,
            new_status=status, note=sanitize(note), author=user.email))
        item.status = status
        item.updated_at = datetime.utcnow()
        db.commit()
        flash(request, f"Solicitação #{item.id} atualizada para “{status}”.")
    return RedirectResponse(f"/admin/solicitacoes/{req_id}", status_code=303)


@router.get("/atendimentos")
def specialized(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    legal = db.query(models.LegalSupport).order_by(models.LegalSupport.created_at.desc()).all()
    psy = db.query(models.PsychologicalSupport).order_by(models.PsychologicalSupport.created_at.desc()).all()
    mei = db.query(models.MeiSupport).order_by(models.MeiSupport.created_at.desc()).all()
    histories = db.query(models.SpecializedSupportHistory)\
        .order_by(models.SpecializedSupportHistory.created_at.desc()).all()
    history_map = build_specialized_history_map(histories)

    def histories_for(kind: str, item_id: int):
        return history_map.get((kind, item_id), [])

    return templates.TemplateResponse(request, "admin/atendimentos.html",
        base_ctx(request, user, legal=legal, psy=psy, mei=mei,
                 histories_for=histories_for))


@router.post("/atendimentos/{kind}/{item_id}/status")
def specialized_status(request: Request, kind: str, item_id: int, status: str = Form(...),
                       note: str = Form(""), db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    model = KIND_MODELS.get(kind)
    if model and status in models.STATUSES:
        item = db.query(model).filter_by(id=item_id).first()
        if item:
            add_specialized_history(db, kind, item.id, item.status, status, note, user.email)
            item.status = status
            db.commit()
            flash(request, "Status atualizado.")
    return RedirectResponse("/admin/atendimentos", status_code=303)


@router.post("/atendimentos/psicologico/{item_id}/agendar")
def psy_schedule(request: Request, item_id: int, scheduled_at: str = Form(""),
                 db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    item = db.query(models.PsychologicalSupport).filter_by(id=item_id).first()
    if not item:
        flash(request, "Pedido não encontrado.")
    elif not scheduled_at.strip():
        item.scheduled_at = None
        db.commit()
        flash(request, "Agendamento removido.")
    elif (when := parse_schedule(sanitize(scheduled_at, 40))):
        item.scheduled_at = when
        db.commit()
        flash(request, "Agendamento confirmado.")
    else:
        flash(request, "Data/hora inválida.")
    return RedirectResponse("/admin/atendimentos", status_code=303)


@router.get("/cursos")
def courses(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    items = db.query(models.Course).order_by(models.Course.title).all()
    return templates.TemplateResponse(request, "admin/cursos.html", base_ctx(request, user, items=items))


@router.post("/cursos")
def course_create(request: Request, title: str = Form(...), description: str = Form(...),
                  category: str = Form(...), workload_hours: int = Form(0),
                  db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    db.add(models.Course(title=sanitize(title, 180), description=sanitize(description),
                         category=sanitize(category, 120), workload_hours=max(0, workload_hours)))
    db.commit()
    flash(request, "Curso cadastrado.")
    return RedirectResponse("/admin/cursos", status_code=303)


@router.post("/cursos/{course_id}/editar")
def course_edit(request: Request, course_id: int, title: str = Form(...),
                description: str = Form(...), category: str = Form(...),
                workload_hours: int = Form(0), active: str = Form(None),
                db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    c = db.query(models.Course).filter_by(id=course_id).first()
    if c:
        c.title, c.description = sanitize(title, 180), sanitize(description)
        c.category, c.workload_hours = sanitize(category, 120), max(0, workload_hours)
        c.active = active == "on"
        db.commit()
        flash(request, "Curso atualizado.")
    return RedirectResponse("/admin/cursos", status_code=303)


@router.get("/cursos/{course_id}/inscritos")
def course_enrollees(request: Request, course_id: int, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    course = db.query(models.Course).filter_by(id=course_id).first()
    if not course:
        return RedirectResponse("/admin/cursos", status_code=303)
    return templates.TemplateResponse(request, "admin/inscritos.html", base_ctx(request, user, course=course))


@router.get("/eventos")
def events(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    items = db.query(models.Event).order_by(models.Event.event_date.desc()).all()
    return templates.TemplateResponse(request, "admin/eventos.html", base_ctx(request, user, items=items))


@router.post("/eventos")
def event_create(request: Request, title: str = Form(...), description: str = Form(""),
                 event_date: str = Form(""), location: str = Form(""),
                 db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    parsed: Optional[datetime] = None
    if event_date:
        try:
            parsed = datetime.fromisoformat(event_date)
        except ValueError:
            parsed = None
    db.add(models.Event(title=sanitize(title, 180), description=sanitize(description),
                        event_date=parsed, location=sanitize(location, 180)))
    db.commit()
    flash(request, "Evento cadastrado.")
    return RedirectResponse("/admin/eventos", status_code=303)


@router.get("/eventos/{event_id}/editar")
def event_edit_form(event_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    event = db.get(models.Event, event_id)
    if not event:
        flash(request, "Evento não encontrado.")
        return RedirectResponse("/admin/eventos", status_code=303)
    return templates.TemplateResponse(request, "admin/eventos.html",
                                      base_ctx(request, user, items=db.query(models.Event)
                                               .order_by(models.Event.event_date.desc()).all(),
                                               editing=event))


@router.post("/eventos/{event_id}/editar")
def event_edit(event_id: int, request: Request, title: str = Form(...),
               description: str = Form(""), event_date: str = Form(""),
               location: str = Form(""), db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    event = db.get(models.Event, event_id)
    if not event:
        flash(request, "Evento não encontrado.")
        return RedirectResponse("/admin/eventos", status_code=303)
    parsed: Optional[datetime] = None
    if event_date:
        try:
            parsed = datetime.fromisoformat(event_date)
        except ValueError:
            parsed = None
    event.title = sanitize(title, 180)
    event.description = sanitize(description)
    event.event_date = parsed
    event.location = sanitize(location, 180)
    db.commit()
    flash(request, "Evento atualizado.")
    return RedirectResponse("/admin/eventos", status_code=303)


@router.post("/eventos/{event_id}/toggle")
def event_toggle(event_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    event = db.get(models.Event, event_id)
    if not event:
        flash(request, "Evento não encontrado.")
        return RedirectResponse("/admin/eventos", status_code=303)
    event.active = not event.active
    db.commit()
    estado = "ativado" if event.active else "desativado"
    flash(request, f"Evento {estado}.")
    return RedirectResponse("/admin/eventos", status_code=303)


@router.get("/parceiros")
def partners(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    items = db.query(models.Partner).order_by(models.Partner.category, models.Partner.name).all()
    return templates.TemplateResponse(request, "admin/parceiros.html", base_ctx(request, user, items=items))


@router.post("/parceiros")
def partner_create(request: Request, name: str = Form(...), category: str = Form(...),
                   discount: str = Form(""), city: str = Form(""), state: str = Form(""),
                   contact: str = Form(""), db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    db.add(models.Partner(name=sanitize(name, 180), category=sanitize(category, 120),
        discount=sanitize(discount, 120), city=sanitize(city, 120),
        state=sanitize(state, 2).upper(), contact=sanitize(contact, 180)))
    db.commit()
    flash(request, "Parceiro cadastrado.")
    return RedirectResponse("/admin/parceiros", status_code=303)


@router.post("/parceiros/{partner_id}/editar")
def partner_edit(request: Request, partner_id: int, name: str = Form(...),
                 category: str = Form(...), discount: str = Form(""), city: str = Form(""),
                 state: str = Form(""), contact: str = Form(""), active: str = Form(None),
                 db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    p = db.query(models.Partner).filter_by(id=partner_id).first()
    if p:
        p.name, p.category = sanitize(name, 180), sanitize(category, 120)
        p.discount, p.city = sanitize(discount, 120), sanitize(city, 120)
        p.state, p.contact = sanitize(state, 2).upper(), sanitize(contact, 180)
        p.active = active == "on"
        db.commit()
        flash(request, "Parceiro atualizado.")
    return RedirectResponse("/admin/parceiros", status_code=303)


@router.get("/admins")
def admins_list(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    admins = db.query(models.User).filter(models.User.role == "admin").order_by(models.User.created_at).all()
    return templates.TemplateResponse(request, "admin/admins.html", base_ctx(request, user, admins=admins))


@router.post("/admins")
def admins_create(request: Request, email: str = Form(...), password: str = Form(...),
                  confirm_password: str = Form(...), db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    email = sanitize(email).lower()
    exists = bool(db.query(models.User).filter(models.User.email == email).first())
    errors = validate_new_admin(email, password, confirm_password, exists)
    if errors:
        flash(request, " ".join(errors), "error")
        return RedirectResponse("/admin/admins", status_code=303)
    db.add(models.User(email=email, password_hash=hash_password(password), role="admin"))
    db.commit()
    flash(request, "Novo administrador criado com sucesso.")
    return RedirectResponse("/admin/admins", status_code=303)

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import base_ctx, flash, get_current_user
from ..validators import sanitize

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/templates")

KIND_MODELS = {"juridico": models.LegalSupport, "psicologico": models.PsychologicalSupport,
               "mei": models.MeiSupport}


def require_admin(request: Request, db: Session):
    user = get_current_user(request, db)
    return user if user and user.role == "admin" else None


def guard(user):
    return RedirectResponse("/login", status_code=303) if user is None else None


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
    return templates.TemplateResponse("admin/dashboard.html", base_ctx(
        request, user, total_affiliates=total_affiliates, by_state=by_state, by_city=by_city,
        by_type=by_type, by_status=by_status, by_profession=by_profession, by_mei=by_mei,
        top_courses=top_courses, open_requests=open_requests))


@router.get("/afiliados")
def affiliates(request: Request, estado: str = "", cidade: str = "", profissao: str = "",
               db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    q = db.query(models.Affiliate)
    if estado:
        q = q.filter(models.Affiliate.state == estado.upper())
    if cidade:
        q = q.filter(models.Affiliate.city.ilike(f"%{sanitize(cidade, 120)}%"))
    if profissao in models.PROFESSIONS:
        q = q.filter(models.Affiliate.profession == profissao)
    items = q.order_by(models.Affiliate.created_at.desc()).all()
    states = [s[0] for s in db.query(models.Affiliate.state).distinct().order_by(models.Affiliate.state)]
    return templates.TemplateResponse("admin/afiliados.html", base_ctx(
        request, user, items=items, states=states,
        f_estado=estado.upper(), f_cidade=cidade, f_profissao=profissao))


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
    return templates.TemplateResponse("admin/afiliado_detalhe.html", base_ctx(
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


@router.get("/solicitacoes")
def requests_list(request: Request, tipo: str = "", status: str = "",
                  db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    q = db.query(models.SupportRequest)
    if tipo in models.REQUEST_TYPES:
        q = q.filter(models.SupportRequest.type == tipo)
    if status in models.STATUSES:
        q = q.filter(models.SupportRequest.status == status)
    items = q.order_by(models.SupportRequest.created_at.desc()).all()
    return templates.TemplateResponse("admin/solicitacoes.html", base_ctx(
        request, user, items=items, f_tipo=tipo, f_status=status))


@router.get("/solicitacoes/{req_id}")
def request_detail(request: Request, req_id: int, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    item = db.query(models.SupportRequest).filter_by(id=req_id).first()
    if not item:
        return RedirectResponse("/admin/solicitacoes", status_code=303)
    return templates.TemplateResponse("admin/solicitacao_detalhe.html", base_ctx(request, user, item=item))


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
    return templates.TemplateResponse("admin/atendimentos.html",
        base_ctx(request, user, legal=legal, psy=psy, mei=mei))


@router.post("/atendimentos/{kind}/{item_id}/status")
def specialized_status(request: Request, kind: str, item_id: int, status: str = Form(...),
                       db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    model = KIND_MODELS.get(kind)
    if model and status in models.STATUSES:
        item = db.query(model).filter_by(id=item_id).first()
        if item:
            item.status = status
            db.commit()
            flash(request, "Status atualizado.")
    return RedirectResponse("/admin/atendimentos", status_code=303)


@router.get("/cursos")
def courses(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    items = db.query(models.Course).order_by(models.Course.title).all()
    return templates.TemplateResponse("admin/cursos.html", base_ctx(request, user, items=items))


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
    return templates.TemplateResponse("admin/inscritos.html", base_ctx(request, user, course=course))


@router.get("/eventos")
def events(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    items = db.query(models.Event).order_by(models.Event.event_date.desc()).all()
    return templates.TemplateResponse("admin/eventos.html", base_ctx(request, user, items=items))


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


@router.get("/parceiros")
def partners(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    if (r := guard(user)):
        return r
    items = db.query(models.Partner).order_by(models.Partner.category, models.Partner.name).all()
    return templates.TemplateResponse("admin/parceiros.html", base_ctx(request, user, items=items))


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

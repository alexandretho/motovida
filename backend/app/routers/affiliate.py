from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import base_ctx, flash, get_current_user
from ..validators import sanitize

router = APIRouter(prefix="/afiliado")
templates = Jinja2Templates(directory="app/templates")


def require_affiliate(request: Request, db: Session):
    user = get_current_user(request, db)
    if not user or user.role != "affiliate" or not user.affiliate:
        return None
    return user


def guard(user):
    return RedirectResponse("/login", status_code=303) if user is None else None


@router.get("")
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = require_affiliate(request, db)
    if (r := guard(user)):
        return r
    aff = user.affiliate
    requests_ = db.query(models.SupportRequest).filter_by(affiliate_id=aff.id)\
        .order_by(models.SupportRequest.created_at.desc()).limit(5).all()
    counts = {
        "abertas": db.query(models.SupportRequest).filter_by(affiliate_id=aff.id)
            .filter(models.SupportRequest.status.in_(["aberta", "em_analise", "em_atendimento"])).count(),
        "cursos": db.query(models.CourseEnrollment).filter_by(affiliate_id=aff.id).count(),
        "juridico": db.query(models.LegalSupport).filter_by(affiliate_id=aff.id).count(),
        "psico": db.query(models.PsychologicalSupport).filter_by(affiliate_id=aff.id).count(),
    }
    return templates.TemplateResponse("affiliate/dashboard.html",
        base_ctx(request, user, aff=aff, requests=requests_, counts=counts))


@router.get("/juridico")
def legal(request: Request, db: Session = Depends(get_db)):
    user = require_affiliate(request, db)
    if (r := guard(user)):
        return r
    items = db.query(models.LegalSupport).filter_by(affiliate_id=user.affiliate.id)\
        .order_by(models.LegalSupport.created_at.desc()).all()
    return templates.TemplateResponse("affiliate/juridico.html", base_ctx(request, user, items=items))


@router.post("/juridico")
def legal_create(request: Request, category: str = Form(...), description: str = Form(...),
                 db: Session = Depends(get_db)):
    user = require_affiliate(request, db)
    if (r := guard(user)):
        return r
    if category not in models.LEGAL_CATEGORIES or not sanitize(description):
        flash(request, "Preencha todos os campos da solicitação jurídica.", "error")
        return RedirectResponse("/afiliado/juridico", status_code=303)
    db.add(models.LegalSupport(affiliate_id=user.affiliate.id, category=category,
                               description=sanitize(description)))
    db.commit()
    flash(request, "Solicitação jurídica registrada. Nossa equipe entrará em contato.")
    return RedirectResponse("/afiliado/juridico", status_code=303)


@router.get("/psicologico")
def psy(request: Request, db: Session = Depends(get_db)):
    user = require_affiliate(request, db)
    if (r := guard(user)):
        return r
    items = db.query(models.PsychologicalSupport).filter_by(affiliate_id=user.affiliate.id)\
        .order_by(models.PsychologicalSupport.created_at.desc()).all()
    return templates.TemplateResponse("affiliate/psicologico.html", base_ctx(request, user, items=items))


@router.post("/psicologico")
def psy_create(request: Request, relation: str = Form(...), preferred_date: str = Form(""),
               description: str = Form(...), db: Session = Depends(get_db)):
    user = require_affiliate(request, db)
    if (r := guard(user)):
        return r
    if relation not in models.PSY_RELATIONS or not sanitize(description):
        flash(request, "Preencha todos os campos do pedido de acolhimento.", "error")
        return RedirectResponse("/afiliado/psicologico", status_code=303)
    db.add(models.PsychologicalSupport(affiliate_id=user.affiliate.id, relation=relation,
        preferred_date=sanitize(preferred_date, 60), description=sanitize(description)))
    db.commit()
    flash(request, "Pedido de acolhimento registrado. Você será contatado para o agendamento.")
    return RedirectResponse("/afiliado/psicologico", status_code=303)


@router.get("/cursos")
def courses(request: Request, db: Session = Depends(get_db)):
    user = require_affiliate(request, db)
    if (r := guard(user)):
        return r
    courses_ = db.query(models.Course).filter_by(active=True).order_by(models.Course.title).all()
    enrolled_ids = {e.course_id for e in user.affiliate.enrollments}
    return templates.TemplateResponse("affiliate/cursos.html",
        base_ctx(request, user, courses=courses_, enrolled_ids=enrolled_ids))


@router.post("/cursos/{course_id}/inscrever")
def enroll(request: Request, course_id: int, db: Session = Depends(get_db)):
    user = require_affiliate(request, db)
    if (r := guard(user)):
        return r
    course = db.query(models.Course).filter_by(id=course_id, active=True).first()
    exists = db.query(models.CourseEnrollment).filter_by(
        course_id=course_id, affiliate_id=user.affiliate.id).first()
    if course and not exists:
        db.add(models.CourseEnrollment(course_id=course_id, affiliate_id=user.affiliate.id))
        db.commit()
        flash(request, f"Inscrição confirmada no curso “{course.title}”.")
    return RedirectResponse("/afiliado/cursos", status_code=303)


@router.get("/mei")
def mei(request: Request, db: Session = Depends(get_db)):
    user = require_affiliate(request, db)
    if (r := guard(user)):
        return r
    items = db.query(models.MeiSupport).filter_by(affiliate_id=user.affiliate.id)\
        .order_by(models.MeiSupport.created_at.desc()).all()
    return templates.TemplateResponse("affiliate/mei.html", base_ctx(request, user, items=items))


@router.post("/mei")
def mei_create(request: Request, topic: str = Form(...), description: str = Form(...),
               db: Session = Depends(get_db)):
    user = require_affiliate(request, db)
    if (r := guard(user)):
        return r
    if topic not in models.MEI_TOPICS or not sanitize(description):
        flash(request, "Preencha todos os campos da solicitação MEI.", "error")
        return RedirectResponse("/afiliado/mei", status_code=303)
    db.add(models.MeiSupport(affiliate_id=user.affiliate.id, topic=topic,
                             description=sanitize(description)))
    db.commit()
    flash(request, "Solicitação de suporte MEI registrada.")
    return RedirectResponse("/afiliado/mei", status_code=303)


@router.get("/ajuda")
def help_center(request: Request, db: Session = Depends(get_db)):
    user = require_affiliate(request, db)
    if (r := guard(user)):
        return r
    items = db.query(models.SupportRequest).filter_by(affiliate_id=user.affiliate.id)\
        .order_by(models.SupportRequest.created_at.desc()).all()
    return templates.TemplateResponse("affiliate/ajuda.html", base_ctx(request, user, items=items))


@router.post("/ajuda")
def help_create(request: Request, type: str = Form(...), priority: str = Form(...),
                description: str = Form(...), db: Session = Depends(get_db)):
    user = require_affiliate(request, db)
    if (r := guard(user)):
        return r
    if type not in models.REQUEST_TYPES or priority not in models.PRIORITIES or not sanitize(description):
        flash(request, "Preencha todos os campos da solicitação.", "error")
        return RedirectResponse("/afiliado/ajuda", status_code=303)
    req = models.SupportRequest(affiliate_id=user.affiliate.id, type=type,
                                priority=priority, description=sanitize(description))
    db.add(req)
    db.flush()
    db.add(models.RequestHistory(request_id=req.id, new_status="aberta",
                                 note="Solicitação aberta pelo afiliado.", author=user.affiliate.full_name))
    db.commit()
    flash(request, f"Solicitação #{req.id} aberta com sucesso.")
    return RedirectResponse("/afiliado/ajuda", status_code=303)


@router.get("/ajuda/{request_id}")
def help_detail(request: Request, request_id: int, db: Session = Depends(get_db)):
    user = require_affiliate(request, db)
    if (r := guard(user)):
        return r
    item = db.query(models.SupportRequest).filter_by(
        id=request_id, affiliate_id=user.affiliate.id).first()
    if not item:
        return RedirectResponse("/afiliado/ajuda", status_code=303)
    return templates.TemplateResponse("affiliate/solicitacao.html", base_ctx(request, user, item=item))

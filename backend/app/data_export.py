"""Exportação dos dados pessoais do afiliado (LGPD, art. 18 – portabilidade/acesso)."""
import json
from datetime import date, datetime

from sqlalchemy import inspect as sa_inspect

from . import models

SENSITIVE_COLUMNS = {"password_hash"}


def row_to_dict(obj) -> dict:
    out = {}
    for col in sa_inspect(obj.__class__).columns:
        if col.key in SENSITIVE_COLUMNS:
            continue
        v = getattr(obj, col.key)
        out[col.key] = v.isoformat() if isinstance(v, (datetime, date)) else v
    return out


def _rows(db, model, **flt):
    return [row_to_dict(r) for r in db.query(model).filter_by(**flt).all()]


def _specialized_history_for_affiliate(db, aff) -> list[dict]:
    """Coleta todo histórico de atendimentos especializados do afiliado."""
    result = []
    for model, kind in [
        (models.LegalSupport, "juridico"),
        (models.PsychologicalSupport, "psicologico"),
        (models.MeiSupport, "mei"),
    ]:
        ids = [r.id for r in db.query(model).filter_by(affiliate_id=aff.id).all()]
        if ids:
            rows = db.query(models.SpecializedSupportHistory).filter(
                models.SpecializedSupportHistory.kind == kind,
                models.SpecializedSupportHistory.item_id.in_(ids),
            ).all()
            result.extend(row_to_dict(r) for r in rows)
    return result


def build_affiliate_export(db, user) -> dict:
    aff = user.affiliate
    reqs = db.query(models.SupportRequest).filter_by(affiliate_id=aff.id).all()
    history = []
    for r in reqs:
        history += _rows(db, models.RequestHistory, request_id=r.id)
    return {
        "exportado_em": datetime.utcnow().isoformat() + "Z",
        "usuario": row_to_dict(user),
        "afiliado": row_to_dict(aff),
        "consentimentos_lgpd": _rows(db, models.LgpdConsent, affiliate_id=aff.id),
        "solicitacoes": [row_to_dict(r) for r in reqs],
        "historico_solicitacoes": history,
        "apoio_juridico": _rows(db, models.LegalSupport, affiliate_id=aff.id),
        "apoio_psicologico": _rows(db, models.PsychologicalSupport, affiliate_id=aff.id),
        "apoio_mei": _rows(db, models.MeiSupport, affiliate_id=aff.id),
        "historico_atendimentos_especializados": _specialized_history_for_affiliate(db, aff),
        "inscricoes_cursos": _rows(db, models.CourseEnrollment, affiliate_id=aff.id),
        "atendimentos_admin": _rows(db, models.Attendance, affiliate_id=aff.id),
    }


def export_json_bytes(data: dict) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str).encode("utf-8")

from secrets import compare_digest, token_urlsafe
from typing import Optional
from fastapi import Request
from sqlalchemy.orm import Session
from . import models

SITE_URL = "https://motovida.syntratech.com.br"
GA_MEASUREMENT_ID = "G-VHCJDB0QNS"

LABELS = {
    "professions": {"motoboy": "Motoboy", "motociclista": "Motociclista", "entregador": "Entregador",
                    "familiar": "Familiar", "outro": "Outro"},
    "mei": {"ja_sou_mei": "Já sou MEI", "quero_abrir_mei": "Quero abrir MEI",
            "preciso_regularizar": "Preciso regularizar", "nao_sei_informar": "Não sei informar"},
    "types": {"social": "Social", "juridico": "Jurídico", "psicologico": "Psicológico",
              "administrativo": "Administrativo", "mei": "MEI", "outro": "Outro"},
    "priorities": {"baixa": "Baixa", "media": "Média", "alta": "Alta", "urgente": "Urgente"},
    "statuses": {"aberta": "Aberta", "em_analise": "Em análise", "em_atendimento": "Em atendimento",
                 "concluida": "Concluída", "cancelada": "Cancelada"},
    "legal": {"acidente_transito": "Acidente de trânsito", "trabalhista": "Dúvida trabalhista",
              "previdenciaria": "Dúvida previdenciária", "orientacao_geral": "Orientação geral"},
    "psy": {"vitima_acidente": "Vítima de acidente", "familiar_vitima": "Familiar de vítima", "outro": "Outro"},
    "mei_topics": {"abertura": "Abertura do MEI", "regularizacao": "Regularização",
                   "duvida_geral": "Dúvida geral", "outro": "Outro"},
}


def get_current_user(request: Request, db: Session) -> Optional[models.User]:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.query(models.User).filter(models.User.id == user_id).first()


def flash(request: Request, message: str, category: str = "success"):
    request.session["flash"] = {"message": message, "category": category}


def pop_flash(request: Request):
    return request.session.pop("flash", None)


def get_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def is_valid_csrf_token(request: Request, token: str | None) -> bool:
    session_token = request.session.get("csrf_token")
    if not session_token or not token:
        return False
    return compare_digest(session_token, token)


def base_ctx(request: Request, user=None, **extra):
    csp_nonce = getattr(request.state, "csp_nonce", "")
    ctx = {
        "request": request,
        "user": user,
        "flash": pop_flash(request),
        "L": LABELS,
        "csrf_token": get_csrf_token(request),
        "csp_nonce": csp_nonce,
        "site_url": SITE_URL,
        "ga_measurement_id": GA_MEASUREMENT_ID,
    }
    ctx.update(extra)
    return ctx

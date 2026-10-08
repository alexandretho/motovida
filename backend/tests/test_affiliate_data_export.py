import json
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app import models  # noqa: E402
from app.data_export import build_affiliate_export, export_json_bytes  # noqa: E402


def _make(db, n):
    u = models.User(email=f"u{n}@t.com", password_hash=f"SECRETHASH{n}", role="affiliate")
    db.add(u)
    db.flush()
    a = models.Affiliate(user_id=u.id, full_name=f"Pessoa {n}", cpf=f"0000000000{n}", email=f"u{n}@t.com", phone="1",
                         whatsapp="1", city="Curitiba", state="PR", profession="motoboy", mei_status="nao_sei_informar")
    db.add(a)
    db.flush()
    db.add(models.SupportRequest(affiliate_id=a.id, type="juridico", description=f"Pedido {n}"))
    legal = models.LegalSupport(affiliate_id=a.id, category="acidente_transito", description=f"Jurídico {n}")
    db.add(legal)
    db.flush()
    db.add(models.SpecializedSupportHistory(
        kind="juridico",
        item_id=legal.id,
        old_status="aberta",
        new_status="em_analise",
        note=f"Histórico especializado {n}",
        author="admin",
    ))
    admin = models.User(email=f"admin{n}@t.com", password_hash=f"ADMINHASH{n}", role="admin")
    db.add(admin)
    db.flush()
    db.add(models.Attendance(affiliate_id=a.id, admin_id=admin.id, notes=f"Atendimento administrativo {n}"))
    db.commit()
    return u


def test_export_has_own_data_without_hash_or_other_users():
    engine = create_engine("sqlite://")
    models.Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    u1, _u2 = _make(db, 1), _make(db, 2)
    raw = export_json_bytes(build_affiliate_export(db, u1)).decode()
    data = json.loads(raw)
    assert data["usuario"]["email"] == "u1@t.com"
    assert "SECRETHASH" not in raw and "password_hash" not in raw
    assert "u2@t.com" not in raw and "Pessoa 2" not in raw and "Pedido 2" not in raw
    assert len(data["solicitacoes"]) == 1
    assert len(data["apoio_juridico"]) == 1
    assert data["historico_atendimentos_especializados"][0]["note"] == "Histórico especializado 1"
    assert "Histórico especializado 2" not in raw
    assert data["atendimentos_admin"][0]["notes"] == "Atendimento administrativo 1"
    assert "Atendimento administrativo 2" not in raw


def test_anonymous_redirected_to_login():
    from fastapi.testclient import TestClient
    from app.main import app
    r = TestClient(app).get("/afiliado/meus-dados", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"

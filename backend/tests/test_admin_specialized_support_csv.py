import csv
import os
import re
import sys
from datetime import datetime
from io import StringIO
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app import models  # noqa: E402
from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.security import hash_password  # noqa: E402


def _make_affiliate(db, n, *, name, email, city):
    user = models.User(
        email=email,
        password_hash=f"AFILIADO_HASH_{n}",
        role="affiliate",
    )
    db.add(user)
    db.flush()
    affiliate = models.Affiliate(
        user_id=user.id,
        full_name=name,
        cpf=f"3000000000{n}",
        email=email,
        phone=f"1190000000{n}",
        whatsapp=f"1199000000{n}",
        city=city,
        state="SP",
        profession="entregador",
        mei_status="nao_sei_informar",
    )
    db.add(affiliate)
    db.flush()
    return affiliate


def _client_with_data():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()
    db.add(models.User(email="admin@teste.com", password_hash=hash_password("senha-admin-123"), role="admin"))
    ana = _make_affiliate(db, 1, name="=Ana Silva", email="ana@example.com", city="+Sao Paulo")
    bruno = _make_affiliate(db, 2, name="Bruno Lima", email="bruno@example.com", city="Santos")
    carla = _make_affiliate(db, 3, name="Carla Souza", email="carla@example.com", city="Campinas")
    db.add(models.LegalSupport(
        affiliate_id=ana.id,
        category="acidente_transito",
        description="Preciso de orientação jurídica sobre acidente. " * 6,
        status="aberta",
        created_at=datetime(2026, 4, 1, 9, 0, 0),
    ))
    db.add(models.PsychologicalSupport(
        affiliate_id=bruno.id,
        relation="vitima_acidente",
        preferred_date="terças pela manhã",
        scheduled_at="@20/04/2026 10:00",
        description="Acolhimento inicial solicitado.",
        status="em_atendimento",
        created_at=datetime(2026, 4, 3, 11, 0, 0),
    ))
    db.add(models.MeiSupport(
        affiliate_id=carla.id,
        topic="regularizacao",
        description="Dúvida sobre regularização do cadastro MEI.",
        status="concluida",
        created_at=datetime(2026, 4, 2, 10, 0, 0),
    ))
    db.commit()
    db.close()

    def fake_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = fake_db
    return TestClient(app)


def _login_admin(client):
    page = client.get("/login")
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
    response = client.post(
        "/login",
        data={"csrf_token": token, "email": "admin@teste.com", "password": "senha-admin-123"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin"


def test_specialized_support_csv_requires_admin_login():
    app.dependency_overrides.clear()
    client = TestClient(app)
    response = client.get("/admin/atendimentos.csv", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_specialized_support_csv_has_link_headers_and_safe_content():
    client = _client_with_data()
    try:
        _login_admin(client)

        page = client.get("/admin/atendimentos")
        assert "/admin/atendimentos.csv" in page.text

        response = client.get("/admin/atendimentos.csv")

        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["pragma"] == "no-cache"
        assert response.headers["content-disposition"] == 'attachment; filename="atendimentos.csv"'
        assert response.headers["content-type"].startswith("text/csv")

        raw = response.text
        parsed = list(csv.DictReader(StringIO(raw)))
        assert [row["tipo"] for row in parsed] == ["psicologico", "mei", "juridico"]
        assert list(parsed[0].keys()) == [
            "tipo", "id", "afiliado_id", "nome", "email", "cidade", "estado", "status",
            "campos_especificos", "scheduled_at", "criado_em",
        ]
        legal = next(row for row in parsed if row["tipo"] == "juridico")
        psy = next(row for row in parsed if row["tipo"] == "psicologico")
        mei = next(row for row in parsed if row["tipo"] == "mei")

        assert legal["nome"] == "'=Ana Silva"
        assert legal["cidade"] == "'+Sao Paulo"
        assert legal["status"] == "aberta"
        assert legal["campos_especificos"].startswith("categoria=acidente_transito; descricao=Preciso")
        assert legal["campos_especificos"].endswith("...")
        assert legal["scheduled_at"] == ""
        assert legal["criado_em"] == "2026-04-01T09:00:00"

        assert psy["nome"] == "Bruno Lima"
        assert psy["status"] == "em_atendimento"
        assert "situacao=vitima_acidente" in psy["campos_especificos"]
        assert "preferencia=terças pela manhã" in psy["campos_especificos"]
        assert psy["scheduled_at"] == "'@20/04/2026 10:00"

        assert mei["status"] == "concluida"
        assert mei["campos_especificos"].startswith("assunto=regularizacao; descricao=Dúvida")

        assert "cpf" not in raw.lower()
        assert "telefone" not in raw.lower()
        assert "whatsapp" not in raw.lower()
        assert "password" not in raw.lower()
        assert "hash" not in raw.lower()
        assert "AFILIADO_HASH" not in raw
    finally:
        app.dependency_overrides.clear()

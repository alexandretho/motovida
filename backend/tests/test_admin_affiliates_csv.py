import csv
import os
import re
import sys
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


def _make_affiliate(db, n, *, name, city, state, profession):
    user = models.User(
        email=f"afiliado{n}@teste.com",
        password_hash=f"AFILIADO_HASH_{n}",
        role="affiliate",
    )
    db.add(user)
    db.flush()
    affiliate = models.Affiliate(
        user_id=user.id,
        full_name=name,
        cpf=f"0000000000{n}",
        email=f"afiliado{n}@teste.com",
        phone=f"1190000000{n}",
        whatsapp=f"1199000000{n}",
        city=city,
        state=state,
        profession=profession,
        mei_status="nao_sei_informar",
        support_needs=f"Necessidade {n}",
    )
    db.add(affiliate)
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
    _make_affiliate(db, 1, name="Ana Silva", city="Sao Paulo", state="SP", profession="entregador")
    _make_affiliate(db, 2, name="Bruno Lima", city="Santos", state="SP", profession="motoboy")
    _make_affiliate(db, 3, name="Carla Souza", city="Curitiba", state="PR", profession="entregador")
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


def test_affiliates_csv_requires_admin_login():
    client = TestClient(app)
    response = client.get("/admin/afiliados.csv", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_affiliates_csv_uses_filters_headers_and_safe_content():
    client = _client_with_data()
    try:
        _login_admin(client)

        page = client.get("/admin/afiliados?estado=sp&cidade=Paulo&profissao=entregador")
        assert "/admin/afiliados.csv?estado=SP&amp;cidade=Paulo&amp;profissao=entregador" in page.text

        response = client.get("/admin/afiliados.csv?estado=sp&cidade=Paulo&profissao=entregador")

        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["pragma"] == "no-cache"
        assert response.headers["content-disposition"] == 'attachment; filename="afiliados.csv"'
        assert response.headers["content-type"].startswith("text/csv")

        raw = response.text
        parsed = list(csv.DictReader(StringIO(raw)))
        assert [row["nome"] for row in parsed] == ["Ana Silva"]
        assert parsed[0]["estado"] == "SP"
        assert parsed[0]["cidade"] == "Sao Paulo"
        assert parsed[0]["profissao"] == "entregador"
        assert parsed[0]["email"] == "afiliado1@teste.com"
        assert "Bruno Lima" not in raw
        assert "Carla Souza" not in raw
        assert "password" not in raw.lower()
        assert "hash" not in raw.lower()
        assert "AFILIADO_HASH" not in raw
    finally:
        app.dependency_overrides.clear()

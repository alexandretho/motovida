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
from app.routers import admin  # noqa: E402
from app.security import hash_password  # noqa: E402


def _make_request(db, n, *, name, type_, priority, status, description, created_at):
    user = models.User(
        email=f"afiliado-csv-{n}@teste.com",
        password_hash=f"AFILIADO_HASH_{n}",
        role="affiliate",
    )
    db.add(user)
    db.flush()
    affiliate = models.Affiliate(
        user_id=user.id,
        full_name=name,
        cpf=f"1000000000{n}",
        email=f"afiliado-csv-{n}@teste.com",
        phone=f"1190000000{n}",
        whatsapp=f"1199000000{n}",
        city="Sao Paulo",
        state="SP",
        profession="entregador",
        mei_status="nao_sei_informar",
    )
    db.add(affiliate)
    db.flush()
    support_request = models.SupportRequest(
        affiliate_id=affiliate.id,
        type=type_,
        priority=priority,
        status=status,
        description=description,
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(support_request)
    return support_request


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
    _make_request(
        db,
        1,
        name="Ana Silva",
        type_="juridico",
        priority="alta",
        status="aberta",
        description="Preciso de orientação jurídica sobre acidente. " * 6,
        created_at=datetime(2026, 2, 1, 9, 30, 0),
    )
    _make_request(
        db,
        2,
        name="Bruno Lima",
        type_="psicologico",
        priority="media",
        status="concluida",
        description="Solicitação psicológica já encerrada.",
        created_at=datetime(2026, 2, 2, 10, 0, 0),
    )
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


def test_support_requests_csv_requires_admin_login():
    app.dependency_overrides.clear()
    client = TestClient(app)
    response = client.get("/admin/solicitacoes.csv", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_support_requests_csv_escapes_formula_like_values():
    assert admin.csv_safe("=2+2") == "'=2+2"
    assert admin.csv_safe("+5511999999999") == "'+5511999999999"
    assert admin.csv_safe("@usuario") == "'@usuario"
    assert admin.csv_safe("texto normal") == "texto normal"


def test_support_requests_csv_uses_filters_headers_and_safe_content():
    client = _client_with_data()
    try:
        _login_admin(client)

        page = client.get("/admin/solicitacoes?tipo=juridico&status=aberta")
        assert "/admin/solicitacoes.csv?tipo=juridico&amp;status=aberta" in page.text

        response = client.get("/admin/solicitacoes.csv?tipo=juridico&status=aberta")

        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["pragma"] == "no-cache"
        assert response.headers["content-disposition"] == 'attachment; filename="solicitacoes.csv"'
        assert response.headers["content-type"].startswith("text/csv")

        raw = response.text
        parsed = list(csv.DictReader(StringIO(raw)))
        assert len(parsed) == 1
        assert parsed[0]["id"] == "1"
        assert parsed[0]["afiliado"] == "Ana Silva"
        assert parsed[0]["email"] == "afiliado-csv-1@teste.com"
        assert parsed[0]["tipo"] == "juridico"
        assert parsed[0]["prioridade"] == "alta"
        assert parsed[0]["status"] == "aberta"
        assert parsed[0]["criado_em"] == "2026-02-01T09:30:00"
        assert parsed[0]["descricao_curta"].startswith("Preciso de orientação jurídica sobre acidente.")
        assert parsed[0]["descricao_curta"].endswith("...")
        assert len(parsed[0]["descricao_curta"]) == 120
        assert list(parsed[0].keys()) == [
            "id", "afiliado", "email", "tipo", "prioridade", "status", "criado_em", "descricao_curta",
        ]
        assert "Bruno Lima" not in raw
        assert "cpf" not in raw.lower()
        assert "telefone" not in raw.lower()
        assert "whatsapp" not in raw.lower()
        assert "password" not in raw.lower()
        assert "hash" not in raw.lower()
        assert "AFILIADO_HASH" not in raw
    finally:
        app.dependency_overrides.clear()

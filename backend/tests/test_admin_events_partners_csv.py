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
    db.add_all([
        models.Event(
            title="=Mutirao de seguranca",
            description="+Orientacao sobre pilotagem segura e primeiros socorros",
            event_date=datetime(2026, 4, 5, 14, 30, 0),
            location="@Praca Central",
            active=True,
            created_at=datetime(2026, 3, 1, 9, 0, 0),
        ),
        models.Event(
            title="Evento inativo",
            description="Arquivo",
            event_date=datetime(2026, 3, 1, 10, 0, 0),
            location="Santos",
            active=False,
            created_at=datetime(2026, 2, 20, 9, 0, 0),
        ),
        models.Partner(
            name="@Oficina Legal",
            category="Oficinas mecanicas",
            discount="+15% em revisoes",
            city="-Sao Paulo",
            state="SP",
            contact="=contato@example.com",
            active=True,
            created_at=datetime(2026, 3, 2, 8, 0, 0),
        ),
        models.Partner(
            name="Farmacia Vida",
            category="Farmacias",
            discount="5% em medicamentos",
            city="Curitiba",
            state="PR",
            contact="41999999999",
            active=False,
            created_at=datetime(2026, 3, 3, 8, 0, 0),
        ),
    ])
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


def test_events_csv_requires_admin_login():
    app.dependency_overrides.clear()
    client = TestClient(app)
    response = client.get("/admin/eventos.csv", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_partners_csv_requires_admin_login():
    app.dependency_overrides.clear()
    client = TestClient(app)
    response = client.get("/admin/parceiros.csv", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_events_csv_has_link_headers_and_safe_content():
    client = _client_with_data()
    try:
        _login_admin(client)

        page = client.get("/admin/eventos")
        assert "/admin/eventos.csv" in page.text

        response = client.get("/admin/eventos.csv")

        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["pragma"] == "no-cache"
        assert response.headers["content-disposition"] == 'attachment; filename="eventos.csv"'
        assert response.headers["content-type"].startswith("text/csv")

        parsed = list(csv.DictReader(StringIO(response.text)))
        assert [row["titulo"] for row in parsed] == ["'=Mutirao de seguranca", "Evento inativo"]
        assert parsed[0]["data"] == "2026-04-05T14:30:00"
        assert parsed[0]["local"] == "'@Praca Central"
        assert parsed[0]["descricao_curta"] == "'+Orientacao sobre pilotagem segura e primeiros socorros"
        assert parsed[0]["status"] == "ativo"
        assert parsed[0]["criado_em"] == "2026-03-01T09:00:00"
        assert parsed[1]["status"] == "inativo"
        assert "password" not in response.text.lower()
        assert "hash" not in response.text.lower()
    finally:
        app.dependency_overrides.clear()


def test_partners_csv_has_link_headers_and_safe_content():
    client = _client_with_data()
    try:
        _login_admin(client)

        page = client.get("/admin/parceiros")
        assert "/admin/parceiros.csv" in page.text

        response = client.get("/admin/parceiros.csv")

        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["pragma"] == "no-cache"
        assert response.headers["content-disposition"] == 'attachment; filename="parceiros.csv"'
        assert response.headers["content-type"].startswith("text/csv")

        parsed = list(csv.DictReader(StringIO(response.text)))
        assert [row["nome"] for row in parsed] == ["Farmacia Vida", "'@Oficina Legal"]
        assert parsed[1]["categoria"] == "Oficinas mecanicas"
        assert parsed[1]["desconto"] == "'+15% em revisoes"
        assert parsed[1]["cidade"] == "'-Sao Paulo"
        assert parsed[1]["estado"] == "SP"
        assert parsed[1]["contato"] == "'=contato@example.com"
        assert parsed[1]["status"] == "ativo"
        assert parsed[0]["status"] == "inativo"
        assert "password" not in response.text.lower()
        assert "hash" not in response.text.lower()
    finally:
        app.dependency_overrides.clear()

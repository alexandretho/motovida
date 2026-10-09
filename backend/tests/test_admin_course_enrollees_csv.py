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


def _make_affiliate(db, n, *, name, email, city, whatsapp):
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
        cpf=f"2000000000{n}",
        email=email,
        phone=f"1190000000{n}",
        whatsapp=whatsapp,
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
    course = models.Course(
        title="=Curso de pilotagem segura",
        description="Capacitação prática",
        category="Trânsito",
        workload_hours=8,
    )
    other_course = models.Course(
        title="Mecânica básica",
        description="Noções de manutenção",
        category="Mecânica",
        workload_hours=4,
    )
    db.add_all([course, other_course])
    db.flush()
    ana = _make_affiliate(
        db,
        1,
        name="@Ana Silva",
        email="ana@example.com",
        city="+Sao Paulo",
        whatsapp="+5511999999999",
    )
    bruno = _make_affiliate(
        db,
        2,
        name="Bruno Lima",
        email="bruno@example.com",
        city="Santos",
        whatsapp="11988887777",
    )
    db.add(models.CourseEnrollment(
        course_id=course.id,
        affiliate_id=ana.id,
        created_at=datetime(2026, 3, 2, 9, 0, 0),
    ))
    db.add(models.CourseEnrollment(
        course_id=other_course.id,
        affiliate_id=bruno.id,
        created_at=datetime(2026, 3, 3, 10, 0, 0),
    ))
    course_id = course.id
    db.commit()
    db.close()

    def fake_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = fake_db
    return TestClient(app), course_id


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


def test_course_enrollees_csv_requires_admin_login():
    app.dependency_overrides.clear()
    client = TestClient(app)
    response = client.get("/admin/cursos/1/inscritos.csv", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_course_enrollees_csv_has_link_headers_and_safe_content():
    client, course_id = _client_with_data()
    try:
        _login_admin(client)

        courses_page = client.get("/admin/cursos")
        assert f"/admin/cursos/{course_id}/inscritos.csv" in courses_page.text

        enrollees_page = client.get(f"/admin/cursos/{course_id}/inscritos")
        assert f"/admin/cursos/{course_id}/inscritos.csv" in enrollees_page.text

        response = client.get(f"/admin/cursos/{course_id}/inscritos.csv")

        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["pragma"] == "no-cache"
        assert response.headers["content-disposition"] == f'attachment; filename="curso-{course_id}-inscritos.csv"'
        assert response.headers["content-type"].startswith("text/csv")

        raw = response.text
        parsed = list(csv.DictReader(StringIO(raw)))
        assert len(parsed) == 1
        assert parsed[0]["curso_id"] == str(course_id)
        assert parsed[0]["curso"] == "'=Curso de pilotagem segura"
        assert parsed[0]["nome"] == "'@Ana Silva"
        assert parsed[0]["email"] == "ana@example.com"
        assert parsed[0]["cidade"] == "'+Sao Paulo"
        assert parsed[0]["estado"] == "SP"
        assert parsed[0]["profissao"] == "entregador"
        assert parsed[0]["whatsapp"] == "'+5511999999999"
        assert parsed[0]["inscrito_em"] == "2026-03-02T09:00:00"
        assert list(parsed[0].keys()) == [
            "curso_id", "curso", "inscricao_id", "afiliado_id", "nome", "email", "cidade", "estado",
            "profissao", "whatsapp", "inscrito_em",
        ]
        assert "Bruno Lima" not in raw
        assert "cpf" not in raw.lower()
        assert "password" not in raw.lower()
        assert "hash" not in raw.lower()
        assert "AFILIADO_HASH" not in raw
    finally:
        app.dependency_overrides.clear()

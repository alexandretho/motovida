import os
import re
import sys
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


def _client_with_course():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    session_factory = sessionmaker(bind=engine)
    models.Base.metadata.create_all(engine)

    db = session_factory()
    user = models.User(email="afiliado@example.test", password_hash=hash_password("senha-segura"))
    affiliate = models.Affiliate(
        user=user,
        full_name="Afiliado de Teste",
        cpf="52998224725",
        phone="11999999999",
        whatsapp="11999999999",
        email="afiliado@example.test",
        city="São Paulo",
        state="SP",
        profession="motoboy",
        mei_status="nao_sei_informar",
    )
    course = models.Course(title="Curso de teste", description="Descrição", category="Segurança")
    inactive_course = models.Course(
        title="Curso inativo", description="Descrição", category="Segurança", active=False
    )
    db.add_all([user, affiliate, course, inactive_course])
    db.commit()
    course_id = course.id
    inactive_course_id = inactive_course.id
    db.close()

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    # Establish the authenticated session through the normal login form.
    login_page = client.get("/login")
    token = re.search(r'name="csrf_token" value="([^"]+)"', login_page.text).group(1)
    login_response = client.post("/login", data={
        "csrf_token": token,
        "email": "afiliado@example.test",
        "password": "senha-segura",
    })
    assert login_response.status_code == 200  # TestClient follows the redirect to the dashboard.
    return client, session_factory, engine, course_id, inactive_course_id


def test_course_enrollment_feedback_for_new_duplicate_and_inactive_course():
    client, session_factory, engine, course_id, inactive_course_id = _client_with_course()
    try:
        page = client.get("/afiliado/cursos")
        token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
        first = client.post(
            f"/afiliado/cursos/{course_id}/inscrever",
            data={"csrf_token": token},
            follow_redirects=True,
        )
        assert first.status_code == 200
        assert "Inscrição confirmada no curso" in first.text

        second = client.post(
            f"/afiliado/cursos/{course_id}/inscrever",
            data={"csrf_token": token},
            follow_redirects=True,
        )
        assert second.status_code == 200
        assert "Você já está inscrito neste curso." in second.text

        inactive = client.post(
            f"/afiliado/cursos/{inactive_course_id}/inscrever",
            data={"csrf_token": token},
            follow_redirects=True,
        )
        assert inactive.status_code == 200
        assert "Este curso não está disponível para inscrição." in inactive.text

        db = session_factory()
        try:
            assert db.query(models.CourseEnrollment).filter_by(course_id=course_id).count() == 1
            assert db.query(models.CourseEnrollment).filter_by(course_id=inactive_course_id).count() == 0
        finally:
            db.close()
    finally:
        app.dependency_overrides.clear()
        models.Base.metadata.drop_all(engine)
        engine.dispose()

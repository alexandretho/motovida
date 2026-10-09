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

from app import models, ratelimit  # noqa: E402
from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import public  # noqa: E402
from app.security import hash_password  # noqa: E402


def csrf_token_from(response) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
    assert match is not None
    return match.group(1)


def make_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    user = models.User(email="afiliado@teste.com", password_hash=hash_password("teste123"), role="affiliate")
    db.add(user)
    db.flush()
    affiliate = models.Affiliate(
        user_id=user.id,
        full_name="Afiliado Teste",
        cpf="12345678909",
        phone="41999999999",
        whatsapp="41999999999",
        email="afiliado@teste.com",
        city="Curitiba",
        state="PR",
        profession="motoboy",
        mei_status="nao_sei_informar",
    )
    db.add(affiliate)
    db.commit()
    db.close()
    return Session


def setup_function():
    ratelimit.clear()
    app.dependency_overrides.clear()


def teardown_function():
    app.dependency_overrides.clear()


def test_password_recovery_helper_creates_admin_request_for_existing_affiliate():
    Session = make_db()
    db = Session()

    created = public.create_password_recovery_request(db, "afiliado@teste.com", "41988887777")

    assert created is True
    req = db.query(models.SupportRequest).one()
    assert req.type == "administrativo"
    assert req.priority == "alta"
    assert req.affiliate.email == "afiliado@teste.com"
    assert "recuperação de senha" in req.description
    assert "41988887777" in req.description
    history = db.query(models.RequestHistory).one()
    assert history.request_id == req.id
    assert history.new_status == "aberta"


def test_password_recovery_helper_reuses_active_self_service_request_statuses():
    for status in public.PASSWORD_RECOVERY_OPEN_STATUSES:
        Session = make_db()
        db = Session()

        assert public.create_password_recovery_request(db, "afiliado@teste.com", "41988887777") is True
        req = db.query(models.SupportRequest).one()
        req.status = status
        db.commit()

        assert public.create_password_recovery_request(db, "afiliado@teste.com", "41977776666") is True

        req = db.query(models.SupportRequest).one()
        assert req.status == status
        assert "41988887777" in req.description
        assert "41977776666" not in req.description
        assert db.query(models.RequestHistory).count() == 1
        db.close()


def test_password_recovery_helper_creates_new_request_when_previous_is_closed():
    Session = make_db()
    db = Session()

    assert public.create_password_recovery_request(db, "afiliado@teste.com", "41988887777") is True
    req = db.query(models.SupportRequest).one()
    req.status = "concluida"
    db.commit()

    assert public.create_password_recovery_request(db, "afiliado@teste.com", "41977776666") is True

    requests = db.query(models.SupportRequest).order_by(models.SupportRequest.id).all()
    assert len(requests) == 2
    assert requests[0].status == "concluida"
    assert requests[1].status == "aberta"
    assert "41977776666" in requests[1].description
    assert db.query(models.RequestHistory).count() == 2


def test_password_recovery_helper_is_silent_for_unknown_email():
    Session = make_db()
    db = Session()

    created = public.create_password_recovery_request(db, "ninguem@example.com", "")

    assert created is False
    assert db.query(models.SupportRequest).count() == 0


def test_password_recovery_route_uses_generic_message_and_valid_csrf():
    Session = make_db()

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    csrf_token = csrf_token_from(client.get("/recuperar-senha"))

    response = client.post(
        "/recuperar-senha",
        data={"csrf_token": csrf_token, "email": "afiliado@teste.com", "phone": "41988887777"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Se o e-mail estiver cadastrado" in response.text
    assert "Token CSRF inválido" not in response.text

    db = Session()
    try:
        assert db.query(models.SupportRequest).count() == 1
    finally:
        db.close()


def test_password_recovery_route_rate_limits():
    Session = make_db()

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    csrf_token = csrf_token_from(client.get("/recuperar-senha"))

    for _ in range(public.PASSWORD_RECOVERY_RATE_LIMIT):
        response = client.post(
            "/recuperar-senha",
            data={"csrf_token": csrf_token, "email": "ninguem@example.com", "phone": ""},
            follow_redirects=False,
        )
        assert response.status_code == 303

    response = client.post(
        "/recuperar-senha",
        data={"csrf_token": csrf_token, "email": "ninguem@example.com", "phone": ""},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert public.PASSWORD_RECOVERY_RATE_LIMIT_MESSAGE in response.text

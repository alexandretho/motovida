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
from app.validators import is_valid_phone  # noqa: E402


def _csrf_token(response) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
    assert match is not None
    return match.group(1)


def test_phone_validation_accepts_national_and_international_formats():
    assert is_valid_phone("(41) 99999-8888")
    assert is_valid_phone("+55 41 99999-8888")


def test_phone_validation_rejects_invalid_lengths_and_letters():
    assert not is_valid_phone("41999-8888")
    assert not is_valid_phone("+55 41 99999-8888 ramal 2")
    assert not is_valid_phone("1234567890123456")


def test_profile_update_rejects_invalid_phone_without_saving():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    models.Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine)

    def override_db():
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    db = session_local()
    try:
        user = models.User(email="perfil@teste.com", password_hash=hash_password("teste123"), role="affiliate")
        db.add(user)
        db.flush()
        affiliate = models.Affiliate(
            user_id=user.id,
            full_name="Pessoa Teste",
            cpf="12345678909",
            email=user.email,
            phone="41999998888",
            whatsapp="41999998888",
            city="Curitiba",
            state="PR",
            profession="motoboy",
            mei_status="nao_sei_informar",
        )
        db.add(affiliate)
        db.commit()

        token = _csrf_token(client.get("/login"))
        login = client.post("/login", data={
            "csrf_token": token,
            "email": user.email,
            "password": "teste123",
        }, follow_redirects=False)
        assert login.status_code == 303

        token = _csrf_token(client.get("/afiliado/perfil"))
        response = client.post("/afiliado/perfil", data={
            "csrf_token": token,
            "full_name": "Pessoa Teste",
            "phone": "abc",
            "whatsapp": "41999998888",
            "city": "Curitiba",
            "state": "PR",
            "profession": "motoboy",
            "mei_status": "nao_sei_informar",
        }, follow_redirects=False)

        db.refresh(affiliate)
        assert response.status_code == 303
        assert response.headers["location"] == "/afiliado/perfil"
        assert affiliate.phone == "41999998888"
    finally:
        db.close()
        app.dependency_overrides.clear()

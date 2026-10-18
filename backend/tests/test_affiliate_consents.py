import os
import re
import sys
from datetime import datetime
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


def _csrf_token(response) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
    assert match is not None
    return match.group(1)


def _make_affiliate(db, n, *, email, password="teste123"):
    user = models.User(email=email, password_hash=hash_password(password), role="affiliate")
    db.add(user)
    db.flush()
    affiliate = models.Affiliate(
        user_id=user.id,
        full_name=f"Pessoa {n}",
        cpf=f"0000000000{n}",
        phone="1",
        whatsapp="1",
        email=email,
        city="Curitiba",
        state="PR",
        profession="motoboy",
        mei_status="nao_sei_informar",
    )
    db.add(affiliate)
    db.flush()
    return user, affiliate


def _client_with_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    models.Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    def override_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app), TestingSessionLocal


def test_consents_route_requires_affiliate_login():
    client = TestClient(app)
    response = client.get("/afiliado/consentimentos", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_affiliate_sees_only_own_lgpd_consents():
    client, SessionLocal = _client_with_db()
    db = SessionLocal()
    try:
        _user1, aff1 = _make_affiliate(db, 1, email="um@teste.com")
        _user2, aff2 = _make_affiliate(db, 2, email="dois@teste.com")
        db.add(models.LgpdConsent(
            affiliate_id=aff1.id,
            accepted=True,
            policy_version="v1",
            ip_address="203.0.113.10",
            accepted_at=datetime(2026, 1, 1, 12, 30),
        ))
        db.add(models.LgpdConsent(
            affiliate_id=aff2.id,
            accepted=True,
            policy_version="v2",
            ip_address="198.51.100.20",
            accepted_at=datetime(2026, 1, 2, 9, 0),
        ))
        db.commit()

        token = _csrf_token(client.get("/login"))
        login = client.post(
            "/login",
            data={"csrf_token": token, "email": "um@teste.com", "password": "teste123"},
            follow_redirects=False,
        )
        assert login.status_code == 303

        response = client.get("/afiliado/consentimentos")
        assert response.status_code == 200
        assert "Consentimentos LGPD" in response.text
        assert "<td>v1</td>" in response.text
        assert "01/01/2026 12:30" in response.text
        assert "203.0.113.10" in response.text
        assert "<td>v2</td>" not in response.text
        assert "198.51.100.20" not in response.text
    finally:
        db.close()
        app.dependency_overrides.clear()

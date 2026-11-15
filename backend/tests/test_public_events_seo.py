import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
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


@pytest.fixture()
def seeded_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine)
    models.Base.metadata.create_all(engine)

    db = TestingSessionLocal()
    db.add_all([
        models.Event(
            id=10,
            title="Mutirão de atendimento",
            description="Ação aberta com orientação jurídica e social.",
            event_date=datetime(2026, 11, 5, 9, 30),
            location="Curitiba/PR",
            active=True,
        ),
        models.Event(
            id=11,
            title="Evento desativado",
            description="Não deve aparecer publicamente.",
            event_date=datetime(2026, 12, 1, 10, 0),
            active=False,
        ),
        models.Event(
            id=12,
            title="Outro mutirão",
            description="Evento na mesma data para validar desempate estável.",
            event_date=datetime(2026, 11, 5, 9, 30),
            location="Londrina/PR",
            active=True,
        ),
        models.Event(
            id=13,
            title="Data a confirmar",
            description="Evento ativo ainda sem data definida.",
            event_date=None,
            location="Campinas/SP",
            active=True,
        ),
        models.Event(
            id=14,
            title="Evento anterior",
            description="Ação já realizada.",
            event_date=datetime.now() - timedelta(days=2),
            location="Santos/SP",
            active=True,
        ),
    ])
    db.commit()
    db.close()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app), TestingSessionLocal
    finally:
        app.dependency_overrides.clear()
        models.Base.metadata.drop_all(engine)


def test_sitemap_includes_active_event_detail_and_lastmod(seeded_client):
    client, _ = seeded_client
    response = client.get("/sitemap.xml")

    assert response.status_code == 200
    assert "<loc>https://motovida.syntratech.com.br/eventos</loc>" in response.text
    assert "<loc>https://motovida.syntratech.com.br/privacidade</loc><lastmod>2026-10-14</lastmod>" in response.text
    assert "<loc>https://motovida.syntratech.com.br/eventos/10</loc>" in response.text
    assert "<loc>https://motovida.syntratech.com.br/eventos/13</loc>" in response.text
    assert "<lastmod>2026-11-05</lastmod>" in response.text
    assert "/eventos/11" not in response.text
    assert response.headers["content-type"].startswith("application/xml")


def test_event_detail_is_public_indexable_and_has_canonical(seeded_client):
    client, _ = seeded_client
    response = client.get("/eventos/10")

    assert response.status_code == 200
    assert "Mutirão de atendimento" in response.text
    assert "Ação aberta com orientação jurídica e social." in response.text
    assert 'rel="canonical" href="https://motovida.syntratech.com.br/eventos/10"' in response.text
    assert "x-robots-tag" not in response.headers


def test_inactive_event_detail_returns_404(seeded_client):
    client, _ = seeded_client
    response = client.get("/eventos/11")

    assert response.status_code == 404


def test_events_page_breaks_equal_date_ties_by_id(seeded_client):
    client, _ = seeded_client
    response = client.get("/eventos")

    assert response.status_code == 200
    assert response.text.index("Mutirão de atendimento") < response.text.index("Outro mutirão")
    assert "Evento desativado" not in response.text


def test_events_page_separates_past_events_from_upcoming_and_undated(seeded_client):
    client, _ = seeded_client
    response = client.get("/eventos")

    assert response.status_code == 200
    assert response.text.index("Eventos MotoVida") < response.text.index("Data a confirmar")
    assert response.text.index("Data a confirmar") < response.text.index("Eventos anteriores")
    assert response.text.index("Eventos anteriores") < response.text.index("Evento anterior")


def test_affiliate_events_page_separates_past_events(seeded_client):
    from app.security import hash_password

    _, session_factory = seeded_client
    db = session_factory()
    user = models.User(email="eventos@teste.example", password_hash=hash_password("senha-segura"))
    affiliate = models.Affiliate(
        user=user,
        full_name="Afiliado de Eventos",
        cpf="52998224725",
        phone="11999999999",
        whatsapp="11999999999",
        email=user.email,
        city="São Paulo",
        state="SP",
        profession="motoboy",
        mei_status="nao_sei_informar",
    )
    db.add_all([user, affiliate])
    db.commit()
    user_email = user.email
    db.close()
    client = TestClient(app)
    import re
    login_page = client.get("/login")
    token = re.search(r'name="csrf_token" value="([^"]+)"', login_page.text).group(1)
    client.post("/login", data={
        "csrf_token": token,
        "email": user_email,
        "password": "senha-segura",
    })
    response = client.get("/afiliado/eventos")

    assert response.status_code == 200
    assert response.text.index("Eventos e ações") < response.text.index("Data a confirmar")
    assert response.text.index("Data a confirmar") < response.text.index("Eventos anteriores")
    assert response.text.index("Eventos anteriores") < response.text.index("Evento anterior")

import os
import sys
from datetime import datetime
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
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        models.Base.metadata.drop_all(engine)


def test_sitemap_includes_active_event_detail_and_lastmod(seeded_client):
    response = seeded_client.get("/sitemap.xml")

    assert response.status_code == 200
    assert "<loc>https://motovida.syntratech.com.br/eventos</loc>" in response.text
    assert "<loc>https://motovida.syntratech.com.br/eventos/10</loc>" in response.text
    assert "<lastmod>2026-11-05</lastmod>" in response.text
    assert "/eventos/11" not in response.text
    assert response.headers["content-type"].startswith("application/xml")


def test_event_detail_is_public_indexable_and_has_canonical(seeded_client):
    response = seeded_client.get("/eventos/10")

    assert response.status_code == 200
    assert "Mutirão de atendimento" in response.text
    assert "Ação aberta com orientação jurídica e social." in response.text
    assert 'rel="canonical" href="https://motovida.syntratech.com.br/eventos/10"' in response.text
    assert "x-robots-tag" not in response.headers


def test_inactive_event_detail_returns_404(seeded_client):
    response = seeded_client.get("/eventos/11")

    assert response.status_code == 404

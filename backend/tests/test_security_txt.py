import os
import sys
from datetime import datetime, timedelta, timezone
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

client = TestClient(app)


@pytest.fixture()
def db_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine)
    models.Base.metadata.create_all(engine)

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


def expires_value(response):
    for line in response.text.splitlines():
        if line.startswith("Expires: "):
            return datetime.fromisoformat(line.removeprefix("Expires: ").replace("Z", "+00:00"))
    raise AssertionError("Expires ausente no security.txt")


def test_well_known_security_txt_is_public_plain_text_with_operational_headers():
    before = datetime.now(timezone.utc) + timedelta(days=179)
    response = client.get("/.well-known/security.txt")
    after = datetime.now(timezone.utc) + timedelta(days=181)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["x-robots-tag"] == "noindex, nofollow"
    assert "Contact: https://motovida.syntratech.com.br/contato" in response.text
    assert "Policy: https://motovida.syntratech.com.br/privacidade" in response.text
    assert "Canonical: https://motovida.syntratech.com.br/.well-known/security.txt" in response.text
    assert "Preferred-Languages: pt-BR" in response.text
    assert before <= expires_value(response) <= after


def test_root_security_txt_mirrors_well_known_content():
    response = client.get("/security.txt")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "Contact: https://motovida.syntratech.com.br/contato" in response.text
    assert "Policy: https://motovida.syntratech.com.br/privacidade" in response.text


def test_security_txt_head_uses_same_headers_without_body():
    response = client.head("/.well-known/security.txt")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-robots-tag"] == "noindex, nofollow"
    assert response.text == ""


def test_robots_and_sitemap_remain_available(db_client):
    robots = db_client.get("/robots.txt")
    sitemap = db_client.get("/sitemap.xml")

    assert robots.status_code == 200
    assert "Sitemap: https://motovida.syntratech.com.br/sitemap.xml" in robots.text
    assert robots.headers["content-type"].startswith("text/plain")
    assert sitemap.status_code == 200
    assert sitemap.headers["content-type"].startswith("application/xml")

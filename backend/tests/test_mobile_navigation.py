import os
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


def test_navigation_toggle_exposes_accessible_state_and_target():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
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
        response = TestClient(app).get("/")
    finally:
        app.dependency_overrides.clear()
        models.Base.metadata.drop_all(engine)
        engine.dispose()

    assert response.status_code == 200
    assert 'aria-label="Abrir menu" aria-expanded="false" aria-controls="site-navigation"' in response.text
    assert '<nav class="nav" id="site-navigation">' in response.text


def test_navigation_script_updates_state_and_supports_escape():
    script_path = BACKEND_DIR / "app" / "static" / "js" / "app.js"
    script = script_path.read_text()

    assert 'menuToggle.setAttribute("aria-expanded", String(open))' in script
    assert 'menuToggle.setAttribute("aria-label", open ? "Fechar menu" : "Abrir menu")' in script
    assert 'event.key === "Escape"' in script
    assert 'event.target.closest("a")' in script

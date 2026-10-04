import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app.routers.affiliate import validate_affiliate_password_change  # noqa: E402
from app.security import hash_password  # noqa: E402


def test_accepts_valid_change():
    h = hash_password("teste123")
    assert validate_affiliate_password_change("teste123", "nova-senha-1", "nova-senha-1", h) == []


def test_rejects_wrong_current():
    h = hash_password("teste123")
    assert "Senha atual incorreta." in validate_affiliate_password_change("x", "nova-senha-1", "nova-senha-1", h)


def test_rejects_weak_mismatch_and_same():
    h = hash_password("teste1234")
    e = validate_affiliate_password_change("teste1234", "curta", "outra", h)
    assert len(e) == 2
    e = validate_affiliate_password_change("teste1234", "teste1234", "teste1234", h)
    assert "Escolha uma senha diferente da atual." in e


def test_password_routes_require_affiliate_login():
    import re
    from fastapi.testclient import TestClient
    from app.database import get_db
    from app.main import app

    class Q:
        def filter(self, *a, **k):
            return self

        def filter_by(self, **k):
            return self

        def first(self):
            return None

    class Db:
        def query(self, model):
            return Q()

    def fake_db():
        yield Db()

    app.dependency_overrides[get_db] = fake_db
    client = TestClient(app)
    try:
        r = client.get("/afiliado/senha", follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/login"
        token = re.search(r'name="csrf_token" value="([^"]+)"', client.get("/login").text).group(1)
        r = client.post("/afiliado/senha", data={"csrf_token": token, "current_password": "a",
                        "new_password": "nova-senha-1", "confirm_password": "nova-senha-1"},
                        follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/login"
    finally:
        app.dependency_overrides.clear()

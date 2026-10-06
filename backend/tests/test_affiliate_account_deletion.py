import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app.routers.affiliate import anonymize_affiliate  # noqa: E402
from app.security import hash_password, verify_password  # noqa: E402


def test_anonymize_clears_personal_data():
    aff = SimpleNamespace(id=7, full_name="João", cpf="12345678909", phone="41999", whatsapp="41999",
                          email="a@b.com", city="Curitiba", support_needs="x")
    old_hash = hash_password("teste123")
    user = SimpleNamespace(id=3, email="a@b.com", password_hash=old_hash, affiliate=aff)

    class Db:
        committed = False

        def commit(self):
            self.committed = True

    db = Db()
    anonymize_affiliate(db, user)
    assert db.committed
    assert aff.full_name != "João" and aff.phone == "" and aff.support_needs is None
    assert "a@b.com" not in (aff.email, user.email) and len(aff.cpf) == 11
    assert not verify_password("teste123", user.password_hash)


def test_delete_routes_require_affiliate_login():
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
        r = client.get("/afiliado/excluir-conta", follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/login"
        token = re.search(r'name="csrf_token" value="([^"]+)"', client.get("/login").text).group(1)
        r = client.post("/afiliado/excluir-conta", data={"csrf_token": token, "current_password": "a"},
                        follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/login"
    finally:
        app.dependency_overrides.clear()

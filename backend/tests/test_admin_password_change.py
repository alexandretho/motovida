import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app.routers.admin import validate_admin_password_change, validate_affiliate_password_reset  # noqa: E402
from app.security import hash_password  # noqa: E402


def test_validate_admin_password_change_accepts_valid_change():
    stored_hash = hash_password("dev-only-change-me")

    errors = validate_admin_password_change("dev-only-change-me", "nova-senha-123", "nova-senha-123", stored_hash)

    assert errors == []


def test_validate_admin_password_change_rejects_wrong_current_password():
    stored_hash = hash_password("dev-only-change-me")

    errors = validate_admin_password_change("errada", "nova-senha-123", "nova-senha-123", stored_hash)

    assert "Senha atual incorreta." in errors


def test_validate_admin_password_change_rejects_weak_or_mismatched_password():
    stored_hash = hash_password("dev-only-change-me")

    errors = validate_admin_password_change("dev-only-change-me", "curta", "diferente", stored_hash)

    assert "A nova senha deve ter pelo menos 8 caracteres." in errors
    assert "A confirmação da nova senha não confere." in errors


def test_validate_admin_password_change_rejects_same_password():
    stored_hash = hash_password("dev-only-change-me")

    errors = validate_admin_password_change("dev-only-change-me", "dev-only-change-me", "dev-only-change-me", stored_hash)

    assert "Escolha uma senha diferente da atual." in errors


def test_validate_affiliate_password_reset_accepts_valid_password():
    assert validate_affiliate_password_reset("nova-senha-123", "nova-senha-123") == []


def test_validate_affiliate_password_reset_rejects_short_or_mismatched():
    errors = validate_affiliate_password_reset("curta", "outra")

    assert "A nova senha deve ter pelo menos 8 caracteres." in errors
    assert "A confirmação da nova senha não confere." in errors


def test_affiliate_password_reset_route_requires_admin_login():
    import re
    from fastapi.testclient import TestClient
    from app.database import get_db
    from app.main import app

    class NoUserQuery:
        def filter(self, *a, **k):
            return self

        def filter_by(self, **k):
            return self

        def first(self):
            return None

    class NoUserDb:
        def query(self, model):
            return NoUserQuery()

    def fake_db():
        yield NoUserDb()

    app.dependency_overrides[get_db] = fake_db
    client = TestClient(app)
    try:
        page = client.get("/login")
        token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
        response = client.post(
            "/admin/afiliados/1/senha",
            data={"csrf_token": token, "new_password": "nova-senha-123", "confirm_password": "nova-senha-123"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/login"
    finally:
        app.dependency_overrides.clear()

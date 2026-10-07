import os
import re
import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app import models  # noqa: E402
from app.routers import auth  # noqa: E402
from app.security import DUMMY_PASSWORD_HASH, hash_password  # noqa: E402


def setup_function():
    auth._login_failures.clear()


def test_failed_logins_are_limited_within_window():
    key = ("127.0.0.1", "user@example.com")

    for attempt in range(auth.LOGIN_FAILURE_LIMIT - 1):
        assert auth.record_failed_login(key, now=float(attempt)) is False

    assert auth.record_failed_login(key, now=10.0) is True
    assert auth.is_login_rate_limited(key, now=11.0) is True


def test_login_rate_limit_is_scoped_by_ip_and_email():
    key = ("127.0.0.1", "user@example.com")
    other_ip = ("192.0.2.10", "user@example.com")
    other_email = ("127.0.0.1", "other@example.com")

    for attempt in range(auth.LOGIN_FAILURE_LIMIT):
        auth.record_failed_login(key, now=float(attempt))

    assert auth.is_login_rate_limited(key, now=20.0) is True
    assert auth.is_login_rate_limited(other_ip, now=20.0) is False
    assert auth.is_login_rate_limited(other_email, now=20.0) is False


def test_login_rate_limit_expires_and_resets():
    key = ("127.0.0.1", "user@example.com")

    for attempt in range(auth.LOGIN_FAILURE_LIMIT):
        auth.record_failed_login(key, now=float(attempt))

    assert auth.is_login_rate_limited(key, now=10.0) is True
    assert auth.is_login_rate_limited(key, now=auth.LOGIN_FAILURE_WINDOW_SECONDS + 1.0) is False

    auth.record_failed_login(key, now=auth.LOGIN_FAILURE_WINDOW_SECONDS + 2.0)
    auth.reset_login_rate_limit(key)

    assert auth.is_login_rate_limited(key, now=auth.LOGIN_FAILURE_WINDOW_SECONDS + 3.0) is False


class EmptyQuery:
    def filter_by(self, **kwargs):
        return self

    def first(self):
        return None


class EmptyDb:
    def query(self, model):
        return EmptyQuery()


class UserQuery:
    def __init__(self, user):
        self.user = user

    def filter_by(self, **kwargs):
        return self

    def first(self):
        return self.user


class UserDb:
    def __init__(self, user):
        self.user = user

    def query(self, model):
        return UserQuery(self.user)


def empty_db():
    yield EmptyDb()


def user_db():
    user = models.User(
        id=42,
        email="user@example.com",
        password_hash=hash_password("senha-correta"),
        role="affiliate",
    )
    yield UserDb(user)


def csrf_token_from(response) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
    assert match is not None
    return match.group(1)


def test_login_route_limits_failures_with_flash_and_valid_csrf():
    app.dependency_overrides[get_db] = empty_db
    client = TestClient(app)

    try:
        response = client.get("/login")
        csrf_token = csrf_token_from(response)

        for _ in range(auth.LOGIN_FAILURE_LIMIT):
            response = client.post(
                "/login",
                data={
                    "csrf_token": csrf_token,
                    "email": "USER@example.com",
                    "password": "senha-incorreta",
                },
                follow_redirects=True,
            )

        assert response.status_code == 200
        assert auth.LOGIN_RATE_LIMIT_MESSAGE in response.text
        assert "Token CSRF inválido" not in response.text
    finally:
        app.dependency_overrides.clear()


def test_login_with_unknown_email_still_verifies_dummy_password_hash(monkeypatch):
    app.dependency_overrides[get_db] = empty_db
    client = TestClient(app)
    seen_hashes = []

    def fake_verify_password(password, stored):
        seen_hashes.append(stored)
        return False

    monkeypatch.setattr(auth, "verify_password", fake_verify_password)

    try:
        response = client.get("/login")
        csrf_token = csrf_token_from(response)
        response = client.post(
            "/login",
            data={
                "csrf_token": csrf_token,
                "email": "nao-existe@example.com",
                "password": "qualquer-senha",
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/login"
        assert seen_hashes == [DUMMY_PASSWORD_HASH]
    finally:
        app.dependency_overrides.clear()


class DummyRequest:
    def __init__(self):
        self.session = {
            "csrf_token": "csrf-antigo",
            "flash": {"message": "mensagem antiga", "category": "success"},
            "user_id": 99,
        }


def test_successful_login_rotates_session_state():
    request = DummyRequest()

    auth.rotate_session_for_login(request, 42)

    assert request.session == {"user_id": 42}


def test_successful_login_invalidates_pre_login_csrf_token():
    app.dependency_overrides[get_db] = user_db
    client = TestClient(app)

    try:
        response = client.get("/login")
        csrf_token = csrf_token_from(response)
        old_session_cookie = client.cookies.get("session")

        response = client.post(
            "/login",
            data={
                "csrf_token": csrf_token,
                "email": "user@example.com",
                "password": "senha-correta",
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/afiliado"
        assert client.cookies.get("session") != old_session_cookie

        response = client.post(
            "/contato",
            data={
                "csrf_token": csrf_token,
                "name": "Visitante Teste",
                "email": "visitante@example.com",
                "subject": "Assunto",
                "message": "Mensagem com tamanho suficiente.",
            },
            follow_redirects=False,
        )

        assert response.status_code == 403
        assert "Token CSRF inválido" in response.text
    finally:
        app.dependency_overrides.clear()

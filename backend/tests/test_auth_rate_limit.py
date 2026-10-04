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
from app.routers import auth  # noqa: E402


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


def empty_db():
    yield EmptyDb()


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

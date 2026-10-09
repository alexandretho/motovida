import os
import re
import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402


def csrf_token_from(response) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
    assert match is not None
    return match.group(1)


def test_logout_is_not_available_by_get():
    client = TestClient(app)

    response = client.get("/logout", follow_redirects=False)

    assert response.status_code == 405
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-robots-tag"] == "noindex, nofollow"


def test_logout_post_requires_valid_csrf_token():
    client = TestClient(app)

    response = client.post("/logout", follow_redirects=False)

    assert response.status_code == 403
    assert "Token CSRF inválido" in response.text


def test_logout_post_with_csrf_clears_session():
    client = TestClient(app)
    token = csrf_token_from(client.get("/login"))
    assert client.cookies.get("session")

    response = client.post("/logout", data={"csrf_token": token}, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert client.cookies.get("session") is None

import os
import re
import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402


def _token(client):
    html = client.get("/login").text
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def test_post_without_csrf_token_is_rejected():
    client = TestClient(app)
    r = client.post("/login", data={"email": "a@b.com", "password": "x"}, follow_redirects=False)
    assert r.status_code == 403


def test_post_with_wrong_csrf_token_is_rejected():
    client = TestClient(app)
    _token(client)
    r = client.post("/login", data={"email": "a@b.com", "password": "x", "csrf_token": "errado"},
                    follow_redirects=False)
    assert r.status_code == 403


def test_post_with_other_session_token_is_rejected():
    token = _token(TestClient(app))
    r = TestClient(app).post("/login", data={"email": "a@b.com", "password": "x", "csrf_token": token},
                             follow_redirects=False)
    assert r.status_code == 403


def test_get_forms_render_token_and_valid_token_passes_csrf():
    client = TestClient(app, raise_server_exceptions=False)
    token = _token(client)
    r = client.post("/login", data={"email": "nao@existe.com", "password": "x", "csrf_token": token},
                    follow_redirects=False)
    assert r.status_code != 403  # passou do CSRF (pode falhar adiante sem MySQL no teste)

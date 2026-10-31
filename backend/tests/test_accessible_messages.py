import os
import re
import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402


def _csrf_token(client):
    html = client.get("/recuperar-senha").text
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def test_error_flash_messages_are_announced_to_screen_readers():
    client = TestClient(app)
    token = _csrf_token(client)

    response = client.post(
        "/recuperar-senha",
        data={"csrf_token": token, "email": "email-invalido", "phone": ""},
        follow_redirects=True,
    )

    assert response.status_code == 400
    assert 'role="alert" aria-live="assertive"' in response.text
    assert "Informe um e-mail válido." in response.text


def test_inline_form_errors_are_announced_to_screen_readers():
    client = TestClient(app)
    token = _csrf_token(client)
    response = client.post(
        "/recuperar-senha",
        data={"csrf_token": token, "email": "email-invalido", "phone": ""},
    )

    assert response.status_code == 400
    assert 'class="alert alert-error" role="alert" aria-live="assertive"' in response.text
    assert "Informe um e-mail válido." in response.text

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app.config import MAX_FORM_BODY_BYTES  # noqa: E402
from app.main import app  # noqa: E402


def test_large_form_post_is_rejected_before_csrf_validation():
    client = TestClient(app)
    oversized_body = b"x" * (MAX_FORM_BODY_BYTES + 1)

    response = client.post(
        "/login",
        content=oversized_body,
        headers={"content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )

    assert response.status_code == 413
    assert response.text == "Payload muito grande."
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-robots-tag"] == "noindex, nofollow"


def test_reasonable_form_post_still_reaches_csrf_validation():
    client = TestClient(app)

    response = client.post(
        "/login",
        content=b"email=a%40b.com&password=x",
        headers={"content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )

    assert response.status_code == 403
    assert response.text == "Token CSRF inválido ou ausente."

import os
import sys
import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app.config import MAX_FORM_BODY_BYTES  # noqa: E402
from app.main import MAX_FORM_FIELDS, app  # noqa: E402


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


def test_post_with_too_many_form_fields_is_rejected():
    client = TestClient(app)
    body = "&".join("x=1" for _ in range(MAX_FORM_FIELDS + 1))

    response = client.post(
        "/login",
        content=body,
        headers={"content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert response.text == "Formulário inválido."


def test_streaming_post_without_content_length_is_stopped_at_body_limit():
    async def scenario():
        delivered = []
        messages = [
            {"type": "http.request", "body": b"x" * MAX_FORM_BODY_BYTES, "more_body": True},
            {"type": "http.request", "body": b"x", "more_body": True},
        ]

        async def receive():
            message = messages.pop(0)
            delivered.append(message)
            return message

        scope = {
            "type": "http", "asgi": {"version": "3.0"},
            "http_version": "1.1", "method": "POST", "scheme": "http",
            "path": "/login", "raw_path": b"/login", "query_string": b"",
            "root_path": "", "headers": [(b"host", b"testserver")],
            "client": ("127.0.0.1", 12345), "server": ("testserver", 80),
        }
        sent = []

        async def send(message):
            sent.append(message)

        await app(scope, receive, send)
        return delivered, sent

    delivered, sent = asyncio.run(scenario())

    response_start = next(message for message in sent if message["type"] == "http.response.start")
    assert response_start["status"] == 413
    assert len(delivered) == 2

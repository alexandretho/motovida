import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402


client = TestClient(app)


def test_default_testclient_host_is_allowed():
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.text == "ok"


def test_localhost_host_header_is_allowed():
    response = client.get("/healthz", headers={"host": "localhost:8000"})

    assert response.status_code == 200
    assert response.text == "ok"


def test_invalid_host_header_is_blocked():
    response = client.get("/healthz", headers={"host": "evil.example"})

    assert response.status_code == 400
    assert response.text == "Invalid host header"

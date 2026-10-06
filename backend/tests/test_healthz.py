import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402


client = TestClient(app)


def test_healthz_is_lightweight_and_cacheable_by_orchestrators():
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.text == "ok"
    assert response.headers["content-type"].startswith("text/plain")


def test_healthz_head_returns_success_without_body():
    response = client.head("/healthz")

    assert response.status_code == 200
    assert response.text == ""
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402

client = TestClient(app)


def test_hsts_present_on_public_route():
    r = client.get("/robots.txt")
    assert r.headers["strict-transport-security"] == "max-age=31536000"
    assert "no-store" not in r.headers.get("cache-control", "")


def test_login_is_not_cacheable():
    r = client.get("/login")
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["pragma"] == "no-cache"


def test_protected_area_redirect_is_not_cacheable():
    r = client.get("/admin", follow_redirects=False)
    assert r.headers["cache-control"] == "no-store"

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402

client = TestClient(app)


def test_html_404_is_friendly():
    r = client.get("/nao-existe", headers={"accept": "text/html"})
    assert r.status_code == 404
    assert "Página não encontrada" in r.text
    assert "Traceback" not in r.text


def test_non_html_404_is_plain():
    r = client.get("/nao-existe", headers={"accept": "application/json"})
    assert r.status_code == 404
    assert "Página não encontrada" not in r.text


def test_scanner_path_still_plain_404():
    r = client.get("/.env", headers={"accept": "text/html"})
    assert r.status_code == 404
    assert "Página não encontrada" not in r.text
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["pragma"] == "no-cache"


def test_public_route_does_not_get_scanner_no_cache_headers():
    r = client.get("/robots.txt")
    assert r.status_code == 200
    assert "User-agent: *" in r.text
    assert r.headers["cache-control"] == "public, max-age=86400"
    assert "pragma" not in r.headers

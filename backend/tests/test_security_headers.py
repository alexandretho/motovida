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
    assert r.headers["cross-origin-opener-policy"] == "same-origin"
    assert r.headers["x-permitted-cross-domain-policies"] == "none"
    assert "no-store" not in r.headers.get("cache-control", "")


def test_login_is_not_cacheable():
    r = client.get("/login")
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["pragma"] == "no-cache"
    assert "Cookie" in r.headers["vary"]
    assert r.headers["x-robots-tag"] == "noindex, nofollow"


def test_public_registration_is_noindex_but_cacheable():
    r = client.get("/cadastro")
    assert r.headers["x-robots-tag"] == "noindex, nofollow"
    assert "Cookie" in r.headers["vary"]
    assert '<meta name="robots" content="noindex, nofollow">' in r.text
    assert "no-store" not in r.headers.get("cache-control", "")


def test_password_recovery_is_noindex_in_headers_and_html():
    r = client.get("/recuperar-senha")
    assert r.headers["x-robots-tag"] == "noindex, nofollow"
    assert '<meta name="robots" content="noindex, nofollow">' in r.text


def test_public_routes_remain_indexable_by_header():
    r = client.get("/robots.txt")
    assert "x-robots-tag" not in r.headers
    assert "vary" not in r.headers


def test_protected_area_redirect_is_not_cacheable():
    r = client.get("/admin", follow_redirects=False)
    assert r.headers["cache-control"] == "no-store"
    assert "Cookie" in r.headers["vary"]
    assert r.headers["x-robots-tag"] == "noindex, nofollow"


def test_public_contact_varies_by_cookie_for_csrf_session():
    r = client.get("/contato")
    assert "Cookie" in r.headers["vary"]
    assert "no-store" not in r.headers.get("cache-control", "")

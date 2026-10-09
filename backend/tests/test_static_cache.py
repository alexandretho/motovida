import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402

client = TestClient(app)


def test_robots_and_favicons_are_cacheable():
    for path in ("/robots.txt", "/favicon.ico", "/favicon.svg"):
        r = client.get(path)
        assert r.status_code == 200
        assert "max-age=86400" in r.headers["cache-control"]

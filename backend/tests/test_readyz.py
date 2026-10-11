import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402


class OkDb:
    def execute(self, *_):
        return 1

    def close(self):
        pass


class BrokenDb(OkDb):
    def execute(self, *_):
        raise RuntimeError("mysql://user:pw-secret@host down")


def _get(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        return TestClient(app).get("/readyz")
    finally:
        app.dependency_overrides.clear()


def test_readyz_ok():
    r = _get(OkDb())
    assert r.status_code == 200
    assert r.json() == {"status": "ready"}
    assert r.headers["cache-control"] == "no-store"


def test_readyz_unavailable_without_leaking():
    r = _get(BrokenDb())
    assert r.status_code == 503
    assert r.json() == {"status": "unavailable"}
    assert "secret" not in r.text
    assert r.headers["cache-control"] == "no-store"

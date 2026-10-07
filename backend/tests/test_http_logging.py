import json
import logging
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402


def http_log_records(caplog):
    return [record for record in caplog.records if record.name == "app.http"]


def test_http_log_uses_trusted_cf_ip_and_omits_query(monkeypatch, caplog):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "1")
    caplog.set_level(logging.INFO, logger="app.http")

    client = TestClient(app)
    response = client.get(
        "/robots.txt?token=segredo&password=123",
        headers={"CF-Connecting-IP": "203.0.113.8"},
    )

    assert response.status_code == 200
    records = http_log_records(caplog)
    assert len(records) == 1
    message = records[0].getMessage()
    data = json.loads(message)
    assert data["event"] == "http_request"
    assert data["method"] == "GET"
    assert data["path"] == "/robots.txt"
    assert data["status_code"] == 200
    assert data["client_ip"] == "203.0.113.8"
    assert isinstance(data["duration_ms"], float)
    assert "?" not in message
    assert "segredo" not in message
    assert "password" not in message


def test_healthz_is_not_logged(caplog):
    caplog.set_level(logging.INFO, logger="app.http")
    response = TestClient(app).get("/healthz?token=segredo")

    assert response.status_code == 200
    assert http_log_records(caplog) == []

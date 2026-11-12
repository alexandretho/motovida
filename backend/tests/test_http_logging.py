import json
import logging
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from fastapi import FastAPI

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app, log_http_requests  # noqa: E402
from app.main import anonymize_ip_for_log  # noqa: E402


def http_log_records(caplog):
    return [record for record in caplog.records if record.name == "app.http"]


def test_http_log_uses_trusted_cf_ip_and_omits_query(monkeypatch, caplog):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "1")
    caplog.set_level(logging.INFO, logger="app.http")

    client = TestClient(app)
    response = client.get(
        "/robots.txt?token=segredo&password=123",
        headers={"CF-Connecting-IP": "203.0.113.8", "X-Request-ID": "req-203_ok.8"},
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-203_ok.8"
    records = http_log_records(caplog)
    assert len(records) == 1
    message = records[0].getMessage()
    data = json.loads(message)
    assert data["event"] == "http_request"
    assert data["method"] == "GET"
    assert data["path"] == "/robots.txt"
    assert data["status_code"] == 200
    assert data["client_ip"] == "203.0.113.0"
    assert data["request_id"] == "req-203_ok.8"
    assert isinstance(data["duration_ms"], float)
    assert "?" not in message
    assert "segredo" not in message
    assert "password" not in message
    assert "203.0.113.8" not in message


def test_anonymize_ip_for_log_masks_ipv4_and_ipv6():
    assert anonymize_ip_for_log("203.0.113.8") == "203.0.113.0"
    assert anonymize_ip_for_log("2001:db8:abcd:1234::42") == "2001:db8:abcd::"
    assert anonymize_ip_for_log("unknown") == "unknown"


def test_request_id_is_generated_when_missing(caplog):
    caplog.set_level(logging.INFO, logger="app.http")

    response = TestClient(app).get("/robots.txt")

    assert response.status_code == 200
    request_id = response.headers["x-request-id"]
    assert len(request_id) == 32
    assert request_id.isalnum()

    records = http_log_records(caplog)
    assert len(records) == 1
    assert json.loads(records[0].getMessage())["request_id"] == request_id


def test_invalid_request_id_is_not_reflected():
    response = TestClient(app).get("/robots.txt", headers={"X-Request-ID": "id com espaco"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] != "id com espaco"
    assert len(response.headers["x-request-id"]) == 32


def test_request_id_with_surrounding_whitespace_is_replaced_and_not_logged(caplog):
    caplog.set_level(logging.INFO, logger="app.http")

    response = TestClient(app).get(
        "/robots.txt", headers={"X-Request-ID": " req-with-space "}
    )

    assert response.status_code == 200
    request_id = response.headers["x-request-id"]
    assert request_id != "req-with-space"
    assert len(request_id) == 32
    data = json.loads(http_log_records(caplog)[0].getMessage())
    assert data["request_id"] == request_id
    assert "req-with-space" not in http_log_records(caplog)[0].getMessage()


def test_healthz_is_not_logged(caplog):
    caplog.set_level(logging.INFO, logger="app.http")
    response = TestClient(app).get("/healthz?token=segredo")

    assert response.status_code == 200
    assert http_log_records(caplog) == []


def test_http_log_records_unhandled_exception_without_exposing_details(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="app.http")

    test_app = FastAPI()
    test_app.middleware("http")(log_http_requests)

    @test_app.get("/failure")
    def fail():
        raise RuntimeError("sensitive failure detail")

    with TestClient(test_app, raise_server_exceptions=False) as client:
        response = client.get("/failure")

    assert response.status_code == 500
    records = http_log_records(caplog)
    assert len(records) == 1
    data = json.loads(records[0].getMessage())
    assert data["status_code"] == 500
    assert data["outcome"] == "exception"
    assert "sensitive failure detail" not in records[0].getMessage()

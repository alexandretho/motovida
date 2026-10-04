import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.ratelimit import client_ip  # noqa: E402


def req(headers):
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host="10.0.0.1"))


def test_ignora_headers_sem_flag(monkeypatch):
    monkeypatch.delenv("TRUST_PROXY_HEADERS", raising=False)
    assert client_ip(req({"cf-connecting-ip": "1.2.3.4"})) == "10.0.0.1"


def test_usa_cf_com_flag(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "1")
    assert client_ip(req({"cf-connecting-ip": "1.2.3.4"})) == "1.2.3.4"
    assert client_ip(req({"x-forwarded-for": "5.6.7.8, 9.9.9.9"})) == "5.6.7.8"


def test_ip_invalido_cai_no_client(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "1")
    assert client_ip(req({"cf-connecting-ip": "lixo"})) == "10.0.0.1"

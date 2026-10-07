import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.ratelimit import client_ip  # noqa: E402


def req(headers, host="10.0.0.1"):
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=host))


def test_ignora_headers_sem_flag(monkeypatch):
    monkeypatch.delenv("TRUST_PROXY_HEADERS", raising=False)
    monkeypatch.delenv("TRUSTED_PROXY_CIDRS", raising=False)
    assert client_ip(req({"cf-connecting-ip": "1.2.3.4"})) == "10.0.0.1"


def test_usa_headers_com_flag_sem_cidrs_para_compatibilidade(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "1")
    monkeypatch.delenv("TRUSTED_PROXY_CIDRS", raising=False)
    assert client_ip(req({"cf-connecting-ip": "1.2.3.4"})) == "1.2.3.4"
    assert client_ip(req({"x-forwarded-for": "5.6.7.8, 9.9.9.9"})) == "5.6.7.8"


def test_usa_cf_quando_proxy_remoto_esta_em_cidr_confiavel(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "1")
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "10.0.0.0/24, 192.0.2.10")
    assert client_ip(req({"cf-connecting-ip": "203.0.113.8"}, host="10.0.0.42")) == "203.0.113.8"


def test_ignora_spoof_quando_proxy_remoto_fora_dos_cidrs(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "1")
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "192.0.2.0/24")
    assert client_ip(req({"cf-connecting-ip": "203.0.113.8"}, host="10.0.0.42")) == "10.0.0.42"


def test_ip_invalido_cai_no_client(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "1")
    monkeypatch.delenv("TRUSTED_PROXY_CIDRS", raising=False)
    assert client_ip(req({"cf-connecting-ip": "lixo"})) == "10.0.0.1"

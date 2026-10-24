import ipaddress
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.ratelimit import client_ip, trusted_proxy_networks  # noqa: E402


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


def test_flag_proxy_aceita_formatos_booleanos_do_config(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", " true ")
    monkeypatch.delenv("TRUSTED_PROXY_CIDRS", raising=False)

    assert client_ip(req({"cf-connecting-ip": "203.0.113.8"})) == "203.0.113.8"


def test_usa_cf_quando_proxy_remoto_esta_em_cidr_confiavel(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "1")
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "10.0.0.0/24, 192.0.2.10")
    assert client_ip(req({"cf-connecting-ip": "203.0.113.8"}, host="10.0.0.42")) == "203.0.113.8"


def test_usa_headers_quando_proxy_remoto_esta_em_preset_private(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "1")
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "private")
    assert client_ip(req({"x-forwarded-for": "203.0.113.9"}, host="172.18.0.5")) == "203.0.113.9"


def test_preset_private_inclui_loopback_e_redes_privadas():
    networks = trusted_proxy_networks("private")

    assert any(ipaddress.ip_address("127.0.0.1") in network for network in networks)
    assert any(ipaddress.ip_address("10.1.2.3") in network for network in networks)
    assert any(ipaddress.ip_address("172.18.0.5") in network for network in networks)
    assert any(ipaddress.ip_address("192.168.10.20") in network for network in networks)
    assert any(ipaddress.ip_address("fc00::1") in network for network in networks)


def test_preset_cloudflare_inclui_cidrs_oficiais_ipv4_e_ipv6():
    networks = trusted_proxy_networks("cloudflare")

    assert len(networks) == 22
    assert any(ipaddress.ip_address("173.245.48.1") in network for network in networks)
    assert any(ipaddress.ip_address("104.16.0.1") in network for network in networks)
    assert any(ipaddress.ip_address("172.64.0.1") in network for network in networks)
    assert any(ipaddress.ip_address("2400:cb00::1") in network for network in networks)
    assert any(ipaddress.ip_address("2a06:98c0::1") in network for network in networks)


def test_usa_headers_quando_proxy_remoto_esta_em_preset_cloudflare(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "1")
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "cloudflare")
    assert client_ip(req({"cf-connecting-ip": "203.0.113.8"}, host="173.245.48.10")) == "203.0.113.8"


def test_presets_private_e_cloudflare_podem_ser_combinados(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "1")
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "private,cloudflare")
    assert client_ip(req({"x-forwarded-for": "203.0.113.9"}, host="172.18.0.5")) == "203.0.113.9"
    assert client_ip(req({"cf-connecting-ip": "203.0.113.8"}, host="2606:4700::1")) == "203.0.113.8"


def test_cidrs_invalidos_sao_ignorados_sem_invalidar_lista(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "1")
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "cidr-invalido, 10.0.0.0/24")
    assert client_ip(req({"cf-connecting-ip": "203.0.113.8"}, host="10.0.0.42")) == "203.0.113.8"


def test_cidrs_configurados_sem_entradas_validas_nao_habilitam_headers(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "yes")
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "cidr-invalido")

    assert client_ip(req({"cf-connecting-ip": "203.0.113.8"}, host="10.0.0.42")) == "10.0.0.42"


def test_ignora_spoof_quando_proxy_remoto_fora_dos_cidrs(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "1")
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "192.0.2.0/24")
    assert client_ip(req({"cf-connecting-ip": "203.0.113.8"}, host="10.0.0.42")) == "10.0.0.42"


def test_ip_invalido_cai_no_client(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "1")
    monkeypatch.delenv("TRUSTED_PROXY_CIDRS", raising=False)
    assert client_ip(req({"cf-connecting-ip": "lixo"})) == "10.0.0.1"

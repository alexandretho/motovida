import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402
from app.config import allowed_hosts_from_env, env_flag, env_int, normalize_allowed_host, normalize_site_url  # noqa: E402


def test_env_flag_defaults_to_false(monkeypatch):
    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    assert env_flag("SESSION_COOKIE_SECURE") is False


def test_env_flag_accepts_common_truthy_values(monkeypatch):
    for value in ("1", "true", "TRUE", "yes", "on", "sim"):
        monkeypatch.setenv("SESSION_COOKIE_SECURE", value)
        assert env_flag("SESSION_COOKIE_SECURE") is True


def test_env_flag_rejects_falsey_or_unknown_values(monkeypatch):
    for value in ("0", "false", "no", "off", "", "qualquer"):
        monkeypatch.setenv("SESSION_COOKIE_SECURE", value)
        assert env_flag("SESSION_COOKIE_SECURE") is False


def test_normalize_site_url_removes_trailing_slash():
    assert normalize_site_url(" https://motovida.example.com.br/ ") == "https://motovida.example.com.br"


def test_normalize_allowed_host_accepts_domains_urls_ports_and_wildcards():
    assert normalize_allowed_host(" https://MotoVida.example.com.br/ ") == "motovida.example.com.br"
    assert normalize_allowed_host("localhost:8000") == "localhost"
    assert normalize_allowed_host("*.example.com.br") == "*.example.com.br"
    assert normalize_allowed_host("*") == "*"


def test_allowed_hosts_include_configured_site_and_local_defaults():
    hosts = allowed_hosts_from_env(
        "admin.example.com.br, https://MotoVida.example.com.br:443",
        "https://motovida.syntratech.com.br/",
    )

    assert hosts == [
        "admin.example.com.br",
        "motovida.example.com.br",
        "motovida.syntratech.com.br",
        "testserver",
        "localhost",
        "127.0.0.1",
    ]


def test_env_int_accepts_bounded_integer(monkeypatch):
    monkeypatch.setenv("MAX_FORM_BODY_BYTES", "32768")
    assert env_int("MAX_FORM_BODY_BYTES", 1024, minimum=1024, maximum=65536) == 32768


def test_env_int_falls_back_for_invalid_or_out_of_bounds(monkeypatch):
    for value in ("abc", "0", "999999"):
        monkeypatch.setenv("MAX_FORM_BODY_BYTES", value)
        assert env_int("MAX_FORM_BODY_BYTES", 4096, minimum=1024, maximum=65536) == 4096


def test_public_site_settings_can_be_configured_by_environment(monkeypatch):
    monkeypatch.setenv("SITE_URL", "https://instituto.example.org/")
    monkeypatch.setenv("GA_MEASUREMENT_ID", "G-TESTE123")
    monkeypatch.setenv("MAX_FORM_BODY_BYTES", "32768")

    reloaded = importlib.reload(config)

    assert reloaded.SITE_URL == "https://instituto.example.org"
    assert "instituto.example.org" in reloaded.ALLOWED_HOSTS
    assert reloaded.GA_MEASUREMENT_ID == "G-TESTE123"
    assert reloaded.MAX_FORM_BODY_BYTES == 32768

    monkeypatch.delenv("SITE_URL", raising=False)
    monkeypatch.delenv("ALLOWED_HOSTS", raising=False)
    monkeypatch.delenv("GA_MEASUREMENT_ID", raising=False)
    monkeypatch.delenv("MAX_FORM_BODY_BYTES", raising=False)
    importlib.reload(config)

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402
from app.config import (  # noqa: E402
    allowed_hosts_from_env,
    env_flag,
    env_int,
    normalize_allowed_host,
    normalize_session_same_site,
    normalize_site_url,
    runtime_config_warnings,
)


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


def test_normalize_session_same_site_accepts_safe_values():
    assert normalize_session_same_site("Strict", secure_cookie=False) == "strict"
    assert normalize_session_same_site("lax", secure_cookie=False) == "lax"
    assert normalize_session_same_site("none", secure_cookie=True) == "none"


def test_normalize_session_same_site_falls_back_for_invalid_or_insecure_none():
    assert normalize_session_same_site("qualquer", secure_cookie=True) == "lax"
    assert normalize_session_same_site("none", secure_cookie=False) == "lax"
    assert normalize_session_same_site("", secure_cookie=True) == "lax"


def test_runtime_config_warnings_flags_insecure_operational_defaults():
    warnings = runtime_config_warnings(
        secret_key="dev-only-change-me",
        admin_password="dev-only-change-me",
        session_cookie_secure=False,
        site_url="https://motovida.example.com.br",
        allowed_hosts=["*"],
    )

    assert len(warnings) == 4
    assert any("SECRET_KEY" in warning for warning in warnings)
    assert any("ADMIN_PASSWORD" in warning for warning in warnings)
    assert any("SESSION_COOKIE_SECURE=1" in warning for warning in warnings)
    assert any("ALLOWED_HOSTS=*" in warning for warning in warnings)


def test_runtime_config_warnings_accepts_hardened_configuration():
    warnings = runtime_config_warnings(
        secret_key="uma-chave-aleatoria-com-mais-de-32-caracteres",
        admin_password="senha-admin-forte-2026",
        session_cookie_secure=True,
        site_url="https://motovida.example.com.br",
        allowed_hosts=["motovida.example.com.br", "localhost"],
    )

    assert warnings == []


def test_public_site_settings_can_be_configured_by_environment(monkeypatch):
    monkeypatch.setenv("SITE_URL", "https://instituto.example.org/")
    monkeypatch.setenv("GA_MEASUREMENT_ID", "G-TESTE123")
    monkeypatch.setenv("MAX_FORM_BODY_BYTES", "32768")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "1")
    monkeypatch.setenv("SESSION_COOKIE_SAME_SITE", "strict")
    monkeypatch.setenv("SESSION_COOKIE_MAX_AGE_SECONDS", "3600")
    monkeypatch.setenv("SECRET_KEY", "uma-chave-aleatoria-com-mais-de-32-caracteres")
    monkeypatch.setenv("ADMIN_PASSWORD", "senha-admin-forte-2026")

    reloaded = importlib.reload(config)

    assert reloaded.SITE_URL == "https://instituto.example.org"
    assert "instituto.example.org" in reloaded.ALLOWED_HOSTS
    assert reloaded.GA_MEASUREMENT_ID == "G-TESTE123"
    assert reloaded.MAX_FORM_BODY_BYTES == 32768
    assert reloaded.SESSION_COOKIE_SECURE is True
    assert reloaded.SESSION_COOKIE_SAME_SITE == "strict"
    assert reloaded.SESSION_COOKIE_MAX_AGE_SECONDS == 3600
    assert reloaded.RUNTIME_CONFIG_WARNINGS == []

    monkeypatch.delenv("SITE_URL", raising=False)
    monkeypatch.delenv("ALLOWED_HOSTS", raising=False)
    monkeypatch.delenv("GA_MEASUREMENT_ID", raising=False)
    monkeypatch.delenv("MAX_FORM_BODY_BYTES", raising=False)
    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    monkeypatch.delenv("SESSION_COOKIE_SAME_SITE", raising=False)
    monkeypatch.delenv("SESSION_COOKIE_MAX_AGE_SECONDS", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    importlib.reload(config)

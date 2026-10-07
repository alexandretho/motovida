import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402
from app.config import env_flag, normalize_site_url  # noqa: E402


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


def test_public_site_settings_can_be_configured_by_environment(monkeypatch):
    monkeypatch.setenv("SITE_URL", "https://instituto.example.org/")
    monkeypatch.setenv("GA_MEASUREMENT_ID", "G-TESTE123")

    reloaded = importlib.reload(config)

    assert reloaded.SITE_URL == "https://instituto.example.org"
    assert reloaded.GA_MEASUREMENT_ID == "G-TESTE123"

    importlib.reload(config)

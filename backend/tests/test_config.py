import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import env_flag  # noqa: E402


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

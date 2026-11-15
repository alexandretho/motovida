import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app import main  # noqa: E402


def test_startup_migrates_schema_before_seeding(monkeypatch):
    calls = []

    class DummySession:
        def close(self):
            calls.append("close")

    monkeypatch.setattr(main, "RUNTIME_CONFIG_WARNINGS", [])
    monkeypatch.setattr(main, "wait_for_db", lambda: calls.append("wait"))
    monkeypatch.setattr(main, "migrate_database", lambda engine: calls.append("migrate"))
    monkeypatch.setattr(main, "SessionLocal", DummySession)
    monkeypatch.setattr(main, "run_seeds", lambda db: calls.append("seed"))

    main.startup()

    assert calls == ["wait", "migrate", "seed", "close"]
    assert main.app.state.startup_complete is True

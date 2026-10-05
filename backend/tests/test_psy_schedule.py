import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import create_engine, inspect, text  # noqa: E402

from app.scheduling import ensure_scheduled_at_column, parse_schedule  # noqa: E402


def test_parse_schedule_formats():
    assert parse_schedule("2026-10-20T14:30") == "20/10/2026 14:30"
    assert parse_schedule("20/10/2026 09:05") == "20/10/2026 09:05"


def test_parse_schedule_rejects_invalid():
    assert parse_schedule("") is None
    assert parse_schedule("amanhã") is None
    assert parse_schedule("2026-13-40T99:99") is None


def test_ensure_column_adds_when_missing_and_is_idempotent():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("CREATE TABLE psychological_support (id INTEGER PRIMARY KEY, description TEXT)"))
    assert ensure_scheduled_at_column(engine) is True
    assert "scheduled_at" in {c["name"] for c in inspect(engine).get_columns("psychological_support")}
    assert ensure_scheduled_at_column(engine) is False


def test_ensure_column_noop_without_table():
    assert ensure_scheduled_at_column(create_engine("sqlite://")) is False

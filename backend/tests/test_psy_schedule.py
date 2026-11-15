import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app.scheduling import parse_schedule  # noqa: E402


def test_parse_schedule_formats():
    assert parse_schedule("2026-10-20T14:30") == "20/10/2026 14:30"
    assert parse_schedule("20/10/2026 09:05") == "20/10/2026 09:05"


def test_parse_schedule_rejects_invalid():
    assert parse_schedule("") is None
    assert parse_schedule("amanhã") is None
    assert parse_schedule("2026-13-40T99:99") is None

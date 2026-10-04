import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app import ratelimit  # noqa: E402


def setup_function():
    ratelimit.clear()


def test_blocks_after_limit_and_resets_after_window():
    for i in range(3):
        assert ratelimit.hit("contato", "1.1.1.1", 3, 60, now=float(i)) is False
    assert ratelimit.hit("contato", "1.1.1.1", 3, 60, now=5.0) is True
    assert ratelimit.hit("contato", "1.1.1.1", 3, 60, now=100.0) is False


def test_scoped_by_ip_and_scope():
    for i in range(3):
        ratelimit.hit("contato", "1.1.1.1", 3, 60, now=float(i))
    assert ratelimit.hit("contato", "2.2.2.2", 3, 60, now=4.0) is False
    assert ratelimit.hit("cadastro", "1.1.1.1", 3, 60, now=4.0) is False

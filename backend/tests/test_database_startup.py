import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app import database  # noqa: E402


class BrokenConnection:
    def __enter__(self):
        raise RuntimeError("mysql+pymysql://user:secret-password@db/motovida")

    def __exit__(self, *_):
        pass


class BrokenEngine:
    def connect(self):
        return BrokenConnection()


def test_wait_for_db_does_not_log_connection_exception_details(monkeypatch, capsys):
    monkeypatch.setattr(database, "engine", BrokenEngine())
    monkeypatch.setattr(database.time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="Não foi possível conectar"):
        database.wait_for_db(retries=1, delay=0)

    output = capsys.readouterr().out
    assert "Aguardando MySQL (1/1)" in output
    assert "RuntimeError" in output
    assert "secret-password" not in output
    assert "mysql+pymysql://" not in output

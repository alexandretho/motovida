import os
import sys
from pathlib import Path
from types import SimpleNamespace

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app.support_history import add_specialized_history, build_specialized_history_map  # noqa: E402


class DummySession:
    def __init__(self):
        self.added = []

    def add(self, item):
        self.added.append(item)


def test_add_specialized_history_sanitizes_note_and_adds_record():
    db = DummySession()

    history = add_specialized_history(
        db,
        "juridico",
        7,
        "aberta",
        "em_analise",
        "  Nota com controle\x00\nok  ",
        "admin@example.invalid",
    )

    assert db.added == [history]
    assert history.kind == "juridico"
    assert history.item_id == 7
    assert history.old_status == "aberta"
    assert history.new_status == "em_analise"
    assert history.note == "Nota com controle\nok"
    assert history.author == "admin@example.invalid"


def test_build_specialized_history_map_groups_by_kind_and_item_id():
    first = SimpleNamespace(kind="mei", item_id=1)
    second = SimpleNamespace(kind="mei", item_id=1)
    other = SimpleNamespace(kind="psicologico", item_id=1)

    history_map = build_specialized_history_map([first, second, other])

    assert history_map[("mei", 1)] == [first, second]
    assert history_map[("psicologico", 1)] == [other]

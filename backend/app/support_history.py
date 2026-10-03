from sqlalchemy.orm import Session

from . import models
from .validators import sanitize


def add_specialized_history(
    db: Session,
    kind: str,
    item_id: int,
    old_status: str | None,
    new_status: str | None,
    note: str = "",
    author: str = "",
):
    history = models.SpecializedSupportHistory(
        kind=kind,
        item_id=item_id,
        old_status=old_status,
        new_status=new_status,
        note=sanitize(note),
        author=author,
    )
    db.add(history)
    return history


def build_specialized_history_map(histories) -> dict:
    history_map = {}
    for history in histories:
        history_map.setdefault((history.kind, history.item_id), []).append(history)
    return history_map

from datetime import datetime

from sqlalchemy import inspect, text


def parse_schedule(value: str):
    """Aceita 'YYYY-MM-DDTHH:MM' ou 'dd/mm/YYYY HH:MM'; devolve 'dd/mm/YYYY HH:MM' ou None."""
    value = (value or "").strip()
    for fmt in ("%Y-%m-%dT%H:%M", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(value, fmt).strftime("%d/%m/%Y %H:%M")
        except ValueError:
            continue
    return None


def ensure_scheduled_at_column(engine) -> bool:
    """Adiciona psychological_support.scheduled_at em bancos existentes (sem Alembic)."""
    insp = inspect(engine)
    if "psychological_support" not in insp.get_table_names():
        return False
    if "scheduled_at" in {c["name"] for c in insp.get_columns("psychological_support")}:
        return False
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE psychological_support ADD COLUMN scheduled_at VARCHAR(60) NULL"))
    return True

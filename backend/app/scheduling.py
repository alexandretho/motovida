from datetime import datetime


def parse_schedule(value: str):
    """Aceita 'YYYY-MM-DDTHH:MM' ou 'dd/mm/YYYY HH:MM'; devolve 'dd/mm/YYYY HH:MM' ou None."""
    value = (value or "").strip()
    for fmt in ("%Y-%m-%dT%H:%M", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(value, fmt).strftime("%d/%m/%Y %H:%M")
        except ValueError:
            continue
    return None

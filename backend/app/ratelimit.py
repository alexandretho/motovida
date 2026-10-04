"""Limitador simples em memória (por processo) para POSTs públicos sensíveis."""
from threading import Lock
from time import monotonic

_hits: dict[tuple[str, str], list[float]] = {}
_lock = Lock()


def client_ip(request) -> str:
    return request.client.host if request.client else "unknown"


def hit(scope: str, ip: str, limit: int, window: float, now: float | None = None) -> bool:
    """Registra uma tentativa. Retorna True se excedeu o limite (bloquear)."""
    now = monotonic() if now is None else now
    with _lock:
        for k in [k for k, v in _hits.items() if not v or now - v[-1] >= window]:
            _hits.pop(k, None)
        times = [t for t in _hits.get((scope, ip), []) if now - t < window]
        if len(times) >= limit:
            _hits[(scope, ip)] = times
            return True
        times.append(now)
        _hits[(scope, ip)] = times
        return False


def clear():
    with _lock:
        _hits.clear()

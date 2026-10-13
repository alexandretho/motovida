"""Limitador simples em memória (por processo) para POSTs públicos sensíveis."""
import ipaddress
import os
from threading import Lock
from time import monotonic

_hits: dict[tuple[str, str], list[float]] = {}
_lock = Lock()

TRUSTED_PROXY_CIDR_PRESETS = {
    "private": (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "127.0.0.0/8",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    ),
}


def trusted_proxy_networks(value: str):
    """Expande CIDRs/presets de proxies confiáveis em redes IP válidas."""
    networks = []
    for raw_entry in value.split(","):
        entry = raw_entry.strip().lower()
        if not entry:
            continue
        entries = TRUSTED_PROXY_CIDR_PRESETS.get(entry, (entry,))
        for cidr in entries:
            try:
                networks.append(ipaddress.ip_network(cidr, strict=False))
            except ValueError:
                continue
    return networks


def client_ip(request) -> str:
    """IP do cliente. Confia em headers de proxy só quando habilitado e permitido."""
    remote_ip = request.client.host if request.client else "unknown"
    if os.getenv("TRUST_PROXY_HEADERS") == "1":
        trusted_proxy_cidrs = os.getenv("TRUSTED_PROXY_CIDRS", "").strip()
        if trusted_proxy_cidrs:
            try:
                remote_addr = ipaddress.ip_address(remote_ip)
                trusted = any(
                    remote_addr in network
                    for network in trusted_proxy_networks(trusted_proxy_cidrs)
                )
            except ValueError:
                trusted = False
            if not trusted:
                return remote_ip

        raw = request.headers.get("cf-connecting-ip") or (
            request.headers.get("x-forwarded-for", "").split(",")[0]
        )
        try:
            return str(ipaddress.ip_address(raw.strip()))
        except ValueError:
            pass
    return remote_ip


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

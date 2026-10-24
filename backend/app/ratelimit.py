"""Limitador simples em memória (por processo) para POSTs públicos sensíveis."""
import ipaddress
import os
from threading import Lock
from time import monotonic

from .config import env_flag

_hits: dict[tuple[str, str], list[float]] = {}
_lock = Lock()

TRUSTED_PROXY_CIDR_PRESETS = {
    "cloudflare": (
        "173.245.48.0/20",
        "103.21.244.0/22",
        "103.22.200.0/22",
        "103.31.4.0/22",
        "141.101.64.0/18",
        "108.162.192.0/18",
        "190.93.240.0/20",
        "188.114.96.0/20",
        "197.234.240.0/22",
        "198.41.128.0/17",
        "162.158.0.0/15",
        "104.16.0.0/13",
        "104.24.0.0/14",
        "172.64.0.0/13",
        "131.0.72.0/22",
        "2400:cb00::/32",
        "2606:4700::/32",
        "2803:f800::/32",
        "2405:b500::/32",
        "2405:8100::/32",
        "2a06:98c0::/29",
        "2c0f:f248::/32",
    ),
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
    if env_flag("TRUST_PROXY_HEADERS"):
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

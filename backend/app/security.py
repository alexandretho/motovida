import hashlib
import hmac
import os
from urllib.parse import unquote

ITERATIONS = 260_000

SENSITIVE_SCANNER_EXACT_PATHS = frozenset({
    "/composer.json",
    "/composer.lock",
    "/debug/default/view",
    "/adminer.php",
    "/wp-login.php",
    "/wp-config.php",
    "/xmlrpc.php",
    "/phpinfo.php",
    "/php_info.php",
    "/i.php",
})

SENSITIVE_SCANNER_PREFIXES = frozenset({
    "/.aws",
    "/.git",
    "/.hg",
    "/.ssh",
    "/.svn",
    "/.idea",
    "/.vscode",
    "/actuator",
    "/cgi-bin",
    "/phpmyadmin",
    "/pma",
    "/server-info",
    "/server-status",
    "/telescope",
    "/vendor",
    "/wp-admin",
    "/wp-content",
    "/wp-includes",
})

SENSITIVE_SCANNER_SEGMENTS = frozenset({
    ".env",
    ".git",
    ".hg",
    ".ssh",
    ".svn",
})

SENSITIVE_SCANNER_FILENAMES = frozenset({
    ".dockercfg",
    ".ds_store",
    ".npmrc",
    "adminer.php",
    "backup.zip",
    "composer.json",
    "composer.lock",
    "config.json",
    "config.php",
    "config.yaml",
    "config.yml",
    "database.sql",
    "db.sql",
    "docker-compose.yaml",
    "docker-compose.yml",
    "dump.sql",
    "id_rsa",
    "package-lock.json",
    "package.json",
    "wp-config.php",
    "yarn.lock",
})


def normalize_scanner_path(path: str) -> str:
    """Normaliza variações comuns usadas por scanners antes do bloqueio."""
    normalized = f"/{path.lstrip('/')}".replace("\\", "/")
    for _ in range(2):
        decoded = unquote(normalized)
        if decoded == normalized:
            break
        normalized = decoded
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    return normalized.lower()


def is_sensitive_scanner_path(path: str) -> bool:
    normalized_path = normalize_scanner_path(path)
    segments = [segment.split(";", 1)[0] for segment in normalized_path.split("/") if segment]

    if normalized_path in SENSITIVE_SCANNER_EXACT_PATHS:
        return True

    if any(
        segment == sensitive or segment.startswith(f"{sensitive}.")
        for segment in segments
        for sensitive in SENSITIVE_SCANNER_SEGMENTS
    ):
        return True

    if any(segment in SENSITIVE_SCANNER_FILENAMES for segment in segments):
        return True

    return any(
        normalized_path == prefix or normalized_path.startswith(f"{prefix}/")
        for prefix in SENSITIVE_SCANNER_PREFIXES
    )


def hash_password(password: str) -> str:
    """PBKDF2-SHA256 — nunca armazena a senha em texto puro."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


# Hash sentinela para manter custo similar quando o e-mail de login não existe.
# Isso reduz enumeração de usuários por diferença de tempo na validação da senha.
DUMMY_PASSWORD_HASH = hash_password("_motovida_dummy_login_password_")


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False

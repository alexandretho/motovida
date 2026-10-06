import hashlib
import hmac
import os

ITERATIONS = 260_000

SENSITIVE_SCANNER_EXACT_PATHS = frozenset({
    "/composer.json",
    "/composer.lock",
    "/debug/default/view",
    "/wp-login.php",
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
    "/actuator",
    "/cgi-bin",
    "/server-info",
    "/server-status",
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


def is_sensitive_scanner_path(path: str) -> bool:
    normalized_path = f"/{path.lstrip('/')}".lower()
    segments = [segment for segment in normalized_path.split("/") if segment]

    if normalized_path in SENSITIVE_SCANNER_EXACT_PATHS:
        return True

    if any(
        segment == sensitive or segment.startswith(f"{sensitive}.")
        for segment in segments
        for sensitive in SENSITIVE_SCANNER_SEGMENTS
    ):
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


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False

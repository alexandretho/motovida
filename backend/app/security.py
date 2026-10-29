import hashlib
import hmac
import os
from urllib.parse import unquote

ITERATIONS = 260_000
MAX_SCANNER_PATH_DECODE_PASSES = 16

SENSITIVE_SCANNER_EXACT_PATHS = frozenset({
    "/composer.json",
    "/composer.lock",
    "/debug/default/view",
    "/debug",
    "/trace.axd",
    "/elmah.axd",
    "/serverinfo",
    "/adminer.php",
    "/wp-login.php",
    "/wp-config.php",
    "/xmlrpc.php",
    "/phpinfo.php",
    "/phpinfo.php3",
    "/phpinfo.phtml",
    "/php-info.php",
    "/php_info.php",
    "/phpversion.php",
    "/test.phpinfo",
    "/i.php",
    "/info.php",
    "/test.php",
    "/phpinfo7.php",
    "/phpinfo8.php",
    "/phpinfo9.php",
    "/phpinf.php",
    "/phpinf.php3",
    "/phpinf.phtml",
    "/phpinf-info.php",
    "/phpinf_info.php",
    "/phpinfversion.php",
    "/phpinf.php",
})

SENSITIVE_SCANNER_PREFIXES = frozenset({
    "/.aws",
    "/.docker",
    "/.kube",
    "/.terraform",
    "/_ignition",
    "/_profiler",
    "/boaform",
    "/console",
    "/ecp",
    "/hudson",
    "/jenkins",
    "/manager",
    "/owa",
    "/solr",
    "/storage/logs",
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
    "/debugbar",
    "/vendor",
    "/wp-admin",
    "/wp-content",
    "/wp-includes",
    "/wp-json",
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
    ".htaccess",
    ".htpasswd",
    ".envrc",
    ".npmrc",
    ".user.ini",
    "adminer.php",
    "backup.tar.gz",
    "backup.zip",
    "bun.lock",
    "bun.lockb",
    "composer.json",
    "composer.lock",
    "config.json",
    "config.php",
    "config.php.dist",
    "config.php.sample",
    "config.php~",
    "config.yaml",
    "config.yml",
    "configuration.php",
    "credentials",
    "credentials.json",
    "database.sql",
    "db.sql",
    "docker-compose.yaml",
    "docker-compose.yml",
    "dump.sql",
    "dump.sql.gz",
    "id_rsa",
    "local_settings.py",
    "package-lock.json",
    "package.json",
    "pnpm-lock.yaml",
    "php_info.php",
    "php-info.php",
    "phpinfo.php",
    "phpinfo.php3",
    "phpinfo.phtml",
    "phpversion.php",
    "info.php",
    "test.php",
    "secrets.json",
    "settings.py",
    "web.config",
    "wp-config.php",
    "wp-config-sample.php",
    "wp-cron.php",
    "wp-login.php",
    "xmlrpc.php",
    "yarn.lock",
})

SENSITIVE_SCANNER_BACKUP_SUFFIXES = (
    "~",
    ".bak",
    ".old",
    ".orig",
    ".save",
    ".swp",
    ".tmp",
    ".backup",
)


def is_sensitive_scanner_prefix(path: str) -> bool:
    for prefix in SENSITIVE_SCANNER_PREFIXES:
        if path == prefix or path.startswith(f"{prefix}/"):
            return True
        if any(
            path == f"{prefix}{suffix}" or path.startswith(f"{prefix}{suffix}/")
            for suffix in SENSITIVE_SCANNER_BACKUP_SUFFIXES
        ):
            return True
    return False


def normalize_scanner_path(path: str) -> str:
    """Normaliza variações comuns usadas por scanners antes do bloqueio."""
    normalized = f"/{path.lstrip('/')}".replace("\\", "/")
    # Repeated encoding is common in scanner evasion probes. Keep decoding
    # bounded, but continue until stable so nested-encoded paths are covered.
    for _ in range(MAX_SCANNER_PATH_DECODE_PASSES):
        decoded = unquote(normalized)
        # A percent-encoded backslash can become a path separator only after
        # decoding (including nested encoding). Normalize it on every pass.
        decoded = decoded.replace("\\", "/")
        if decoded == normalized:
            break
        normalized = decoded
    # A decoded question mark begins the query string to ASGI servers; ignore
    # that suffix so scanner probes cannot hide a sensitive path behind it.
    normalized = normalized.split("?", 1)[0]
    # NUL bytes are rejected or treated as terminators by common web server
    # and filesystem stacks. Match the path they may expose before the NUL.
    normalized = normalized.split("\x00", 1)[0]
    # Do not let the decode limit turn a still-encoded probe into an ordinary
    # route. The caller blocks these paths; preserving the marker also avoids
    # accidentally treating arbitrary percent text as a sensitive filename.
    if "%" in normalized:
        return normalized + "/__encoded_path_depth_exceeded__"
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    # Collapse dot segments after decoding so traversal probes are checked
    # against the same path that a typical proxy or web server would resolve.
    segments = []
    for segment in normalized.split("/"):
        if not segment or segment == ".":
            continue
        if segment == "..":
            if segments:
                segments.pop()
            continue
        segments.append(segment)
    normalized = "/" + "/".join(segments)
    return normalized.lower()


def is_sensitive_scanner_filename(filename: str) -> bool:
    # phpinfo is probed with and without a PHP extension, sometimes with a
    # numeric suffix (for example phpinfo7.php). Keep the match specific to
    # that probe family so ordinary names such as /info.php stay available.
    candidate = filename
    # Backup suffixes are often stacked by scanners or deployment tooling
    # (for example phpinfo.php.bak.old). Strip the whole chain before checking
    # the known probe families; this remains filename-specific and does not
    # match descriptive or unrelated route names.
    while True:
        for suffix in SENSITIVE_SCANNER_BACKUP_SUFFIXES:
            if candidate.endswith(suffix):
                candidate = candidate[: -len(suffix)]
                break
        else:
            break

    # These short phpinfo aliases are common scanner probes. Accept the same
    # PHP extension variants and numeric suffixes as the phpinfo family above.
    phpinfo_alias, alias_separator, alias_extension = candidate.partition(".")
    if phpinfo_alias in {"php_info", "phpinf", "phpinf_info", "php-info", "i"} or any(
        phpinfo_alias.startswith(prefix) and phpinfo_alias[len(prefix):].isdigit()
        for prefix in ("php_info", "phpinf", "php-info", "i")
    ):
        return not alias_separator or alias_extension in {
            "php", "php3", "php4", "php5", "php7", "php8", "php9", "phtml", "phar", "phps"
        }

    phpinfo_stem, separator, extension = candidate.partition(".")
    if phpinfo_stem == "phpinfo" or (
        phpinfo_stem.startswith("phpinfo")
        and phpinfo_stem[len("phpinfo"):].isdigit()
    ):
        # Scanners try several executable PHP extensions and occasionally
        # encode the dot. The path is decoded before this function is called.
        return not separator or extension in {
            "php", "php3", "php4", "php5", "php7", "php8", "php9", "phtml", "phar", "phps"
        }

    # Diagnostic scripts are commonly exposed under these exact filenames.
    # Keep them exact so ordinary application routes like /test-report.php
    # and /info-api.php remain routable.
    if candidate in {"info.php", "test.php"}:
        return True

    if filename in SENSITIVE_SCANNER_FILENAMES:
        return True

    return any(
        filename.endswith(suffix)
        and filename[: -len(suffix)] in SENSITIVE_SCANNER_FILENAMES
        for suffix in SENSITIVE_SCANNER_BACKUP_SUFFIXES
    )


def is_sensitive_scanner_segment(segment: str) -> bool:
    candidate = segment
    while True:
        for suffix in SENSITIVE_SCANNER_BACKUP_SUFFIXES:
            if candidate.endswith(suffix):
                candidate = candidate[: -len(suffix)]
                break
        else:
            break

    if any(
        candidate == sensitive or candidate.startswith(f"{sensitive}.")
        for sensitive in SENSITIVE_SCANNER_SEGMENTS
    ):
        return True

    return candidate in {".gitmodules", ".gitconfig"}


def is_sensitive_scanner_path(path: str) -> bool:
    normalized_path = normalize_scanner_path(path)
    if normalized_path.endswith("/__encoded_path_depth_exceeded__"):
        return True
    segments = [
        segment.split(";", 1)[0]
        for segment in normalized_path.split("/")
        if segment
    ]
    path_without_parameters = "/" + "/".join(segments)

    if normalized_path in SENSITIVE_SCANNER_EXACT_PATHS:
        return True

    if any(is_sensitive_scanner_segment(segment) for segment in segments):
        return True

    if any(is_sensitive_scanner_filename(segment) for segment in segments):
        return True

    return is_sensitive_scanner_prefix(path_without_parameters)


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

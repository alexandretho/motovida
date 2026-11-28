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
    "/xmlrpc",
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
    ".env.example",
    ".env.sample",
    ".env.backup",
    ".env.bak",
    ".dockercfg",
    ".ds_store",
    ".gitignore",
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
    "id_ed25519",
    "id_ecdsa",
    "id_dsa",
    "authorized_keys",
    "known_hosts",
    "config.toml",
    "application.properties",
    "application.yml",
    "application.yaml",
    "credentials.xml",
    ".gitlab-ci.yml",
    "terraform.tfstate",
    "terraform.tfstate.backup",
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
    "wp-admin.php",
    "wp-cron.php",
    "wp-login.php",
    "xmlrpc.php",
    "yarn.lock",
})

SENSITIVE_SCANNER_BACKUP_SUFFIXES = (
    "~",
    ".bak",
    ".bkp",
    ".old",
    ".orig",
    ".save",
    ".swp",
    ".tmp",
    ".backup",
)


def is_sensitive_scanner_prefix(path: str) -> bool:
    # Prefix matching must be case-insensitive, just like filename matching
    # after normalize_scanner_path. Keep this scoped to the first segment so
    # ordinary application routes containing similar words remain routable.
    prefix_segment = path.lstrip("/").partition("/")[0].lower()
    for prefix in SENSITIVE_SCANNER_PREFIXES:
        candidate = prefix_segment
        while True:
            for suffix in SENSITIVE_SCANNER_BACKUP_SUFFIXES:
                if candidate.endswith(suffix):
                    candidate = candidate[: -len(suffix)]
                    break
            else:
                break
        if candidate == prefix.lstrip("/"):
            return True
    return False


def normalize_scanner_path(path: str) -> str:
    """Normaliza variações comuns usadas por scanners antes do bloqueio."""
    # Some intermediaries normalize Unicode slash lookalikes into path
    # separators. Canonicalize common fraction and division slashes before checking.
    normalized = (
        f"/{path.lstrip('/')}"
        .replace("\\", "/")
        .replace("\u2044", "/")
        .replace("\u2215", "/")
        # NFKC normalization in some proxies/frameworks maps the fullwidth
        # solidus to an ASCII path separator. Canonicalize it before matching.
        .replace("\uff0f", "/")
    )
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
    # If the bounded decoder stopped while a traversal marker remains, a
    # proxy/server with a deeper decoding limit could still resolve it. Treat
    # unresolved dot-segment encodings as traversal and fail closed, while
    # leaving unrelated encoded route characters alone.
    if any(
        segment.lower() in {"%2e", ".%2e", "%2e.", "%2e%2e"}
        for segment in normalized.replace("\\", "/").split("/")
    ):
        return "/__encoded_traversal__"
    # HTTP intermediaries and legacy parsers may discard ASCII control bytes
    # embedded in a path segment. Remove them before matching so controls
    # cannot disguise a scanner prefix such as /wp-admin%0a/setup.php.
    normalized = "".join(char for char in normalized if char == "\x00" or (ord(char) >= 0x20 and ord(char) != 0x7f))
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
    # Environment files use many deployment-specific names (.env.staging,
    # .env.production.local, etc.). Treat every file in this family as
    # sensitive while keeping similarly named application files available.
    if filename == ".env" or filename.startswith(".env."):
        return True

    # phpinfo probes are also split across path segments (for example
    # /phpinfo/.php or /phpinfo/php). Treat those equivalent segments as a
    # probe without matching descriptive names such as /phpinfo-api.php.
    phpinfo_segment = filename.replace("_", "").replace("-", "")
    if phpinfo_segment in {"phpinfo", "phpinf", "phpversion", "i"}:
        return True

    # phpinfo and its short /i alias are probed with PHP version extensions
    # (for example phpinfo7.php and i.php5.6). Keep matching filename-specific
    # so descriptive application names remain available.
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

    # These phpinfo aliases are common scanner probes. Accept one optional
    # underscore or hyphen inside the stem, as well as extension/numeric
    # variants, while keeping matching scoped to the known probe family.
    phpinfo_alias, alias_separator, alias_extension = candidate.partition(".")
    alias_stem = phpinfo_alias.replace("_", "").replace("-", "")
    php_version_extension = alias_extension.startswith("php") and all(
        part.isdigit() for part in alias_extension[3:].split(".")
    ) and bool(alias_extension[3:])
    if alias_stem in {"phpinfo", "phpinf", "phpversion", "i"} or any(
        alias_stem.startswith(prefix) and alias_stem[len(prefix):].isdigit()
        for prefix in ("phpinfo", "phpinf", "phpversion", "i")
    ):
        # Scanner wordlists and backup tools sometimes append a harmless
        # looking second extension (for example phpinfo.php.txt). Match only
        # known probe extensions followed by a small set of file suffixes;
        # descriptive names such as phpinfo-report.php remain routable.
        secondary_suffix = {"txt", "html", "htm", "json", "xml", "log"}
        if alias_separator and "." in alias_extension:
            first_extension, _, second_extension = alias_extension.partition(".")
            if (
                first_extension in {
                    "php", "php3", "php4", "php5", "php7", "php8", "php9",
                    "phtml", "phar", "phps", "inc",
                }
                and second_extension in secondary_suffix
            ):
                return True
        # A second alias-like suffix (for example phpinfo.phpinfo or i.i)
        # is also used by scanner lists as a filename variant. Match it only
        # after an already recognized alias stem to avoid broadening names.
        if alias_separator and alias_extension in {
            "phpinfo", "phpinf", "phpversion", "i",
        }:
            return True
        if (
            (
                alias_stem.startswith("phpinfo") and alias_stem[len("phpinfo"):].isdigit()
                or alias_stem.startswith("phpinf") and alias_stem[len("phpinf"):].isdigit()
                or alias_stem.startswith("phpversion") and alias_stem[len("phpversion"):].isdigit()
                or alias_stem.startswith("i") and alias_stem[1:].isdigit()
            )
            and alias_separator
            and alias_extension == "json"
        ):
            return True
        return not alias_separator or alias_extension in {
            "php", "php3", "php4", "php5", "php7", "php8", "php9", "phtml", "phar", "phps", "inc"
        } or php_version_extension

    phpinfo_stem, separator, extension = candidate.partition(".")
    if phpinfo_stem == "phpinfo" or (
        phpinfo_stem.startswith("phpinfo")
        and phpinfo_stem[len("phpinfo"):].isdigit()
    ):
        # Scanners try several executable PHP extensions and occasionally
        # encode the dot. The path is decoded before this function is called.
        return not separator or extension in {
            "php", "php3", "php4", "php5", "php7", "php8", "php9", "phtml", "phar", "phps", "inc"
        } or (
            extension.startswith("php")
            and bool(extension[3:])
            and all(part.isdigit() for part in extension[3:].split("."))
        )

    # Diagnostic scripts are commonly exposed under these exact filenames.
    # Keep them exact so ordinary application routes like /test-report.php
    # and /info-api.php remain routable.
    if candidate in {"info.php", "test.php"}:
        return True

    return candidate in SENSITIVE_SCANNER_FILENAMES


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

    # Git metadata probes also target sibling filenames such as .git-HEAD
    # and .git-credentials. Keep this scoped to the .git namespace.
    if candidate.startswith(".git-"):
        return True

    return candidate in {".gitmodules", ".gitconfig"}


def is_sensitive_scanner_path(path: str) -> bool:
    normalized_path = normalize_scanner_path(path)
    if normalized_path.endswith("/__encoded_path_depth_exceeded__"):
        return True
    # A scanner prefix stays sensitive when traversal would normalize it away.
    # Some proxies resolve the path before routing, while others inspect the
    # original path, so do not let the normalized target hide the probe.
    original_path = f"/{path.lstrip('/')}".replace("\\", "/").lower()
    # Decode the raw path separately for the original-prefix check. The
    # normalized path can erase a sensitive prefix through traversal, while
    # the raw path may still contain encoded separators that upstream servers
    # decode before applying their own routing rules.
    original_path_decoded = original_path
    for _ in range(MAX_SCANNER_PATH_DECODE_PASSES):
        decoded = unquote(original_path_decoded).replace("\\", "/")
        if decoded == original_path_decoded:
            break
        original_path_decoded = decoded
    # Legacy servers and filesystem APIs may terminate a path at a decoded
    # NUL byte. Check that effective prefix too: otherwise a suffix after NUL
    # can make the full normalized path look harmless (for example
    # ``/.env%00ignored``).
    for candidate in (original_path_decoded, normalize_scanner_path(original_path_decoded)):
        if "\x00" in candidate and is_sensitive_scanner_path(candidate.split("\x00", 1)[0]):
            return True
    original_path_without_parameters = "/".join(
        segment.split(";", 1)[0] for segment in original_path.split("/")
    )
    original_path_decoded_without_parameters = "/".join(
        segment.split(";", 1)[0] for segment in original_path_decoded.split("/")
    )
    original_decoded_segments = [
        segment.split(";", 1)[0] for segment in original_path_decoded.split("/")
    ]
    original_windows_trimmed_segments = [
        segment.rstrip(". ") for segment in original_decoded_segments
    ]
    if any(
        candidate == prefix or candidate.startswith(f"{prefix}/")
        for prefix in SENSITIVE_SCANNER_PREFIXES
        for candidate in (
            original_path,
            original_path_without_parameters,
            original_path_decoded,
            original_path_decoded_without_parameters,
        )
    ):
        return True
    if any(
        is_sensitive_scanner_prefix("/" + segment)
        for segment in (*original_decoded_segments, *original_windows_trimmed_segments)
    ):
        return True
    # Some servers ignore path parameters while resolving a filename. Check
    # each filename both as requested and with its matrix parameters removed,
    # so aliases such as /i;v=1.php cannot evade the scanner family match.
    segments = [segment for segment in normalized_path.split("/") if segment]
    parameter_free_segments = [segment.split(";", 1)[0] for segment in segments]
    path_without_parameters = "/" + "/".join(parameter_free_segments)
    # Windows/IIS commonly trims trailing dots and spaces from path segments
    # before resolving them. Check that alias for scanner names and prefixes.
    windows_trimmed_segments = [segment.rstrip(". ") for segment in parameter_free_segments]

    if normalized_path in SENSITIVE_SCANNER_EXACT_PATHS:
        return True

    if any(is_sensitive_scanner_segment(segment) for segment in parameter_free_segments):
        return True

    if any(is_sensitive_scanner_segment(segment) for segment in windows_trimmed_segments):
        return True

    # Sensitive service prefixes can also appear below an application mount
    # point (for example /tenant/wp-admin/...). Check every directory segment
    # after decoding so encoded prefix names cannot evade the prefix rule.
    if any(
        is_sensitive_scanner_prefix("/" + segment)
        for segment in parameter_free_segments
    ):
        return True

    # Some path normalizers strip a trailing dot from a segment. Check that
    # alias for known scanner prefixes without changing general route matching.
    if any(
        is_sensitive_scanner_prefix("/" + segment.rstrip("."))
        for segment in parameter_free_segments
        if segment.endswith(".")
    ):
        return True

    if any(is_sensitive_scanner_prefix("/" + segment) for segment in windows_trimmed_segments):
        return True

    # phpinfo diagnostic aliases nested under known scanner endpoints are
    # common probes too; block them even when the base filename is nested.
    if (
        any(is_sensitive_scanner_prefix("/" + segment) for segment in parameter_free_segments[:-1])
        and any(is_sensitive_scanner_filename(segment) for segment in parameter_free_segments[-1:])
    ):
        return True

    if any(
        is_sensitive_scanner_filename(segment)
        for segment in (*segments, *parameter_free_segments)
    ):
        return True

    if any(is_sensitive_scanner_filename(segment) for segment in windows_trimmed_segments):
        return True

    # Prefix probes can carry matrix parameters on the directory segment.
    # Check the parameter-free path so e.g. /wp-admin;v=1/unknown cannot
    # bypass a prefix rule that applies to /wp-admin.
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

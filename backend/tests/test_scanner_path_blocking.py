import os
import sys
import json
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402
from app.security import is_sensitive_scanner_path  # noqa: E402


client = TestClient(app)


def test_blocked_scanner_attempt_is_logged_without_probe_path_or_query(monkeypatch, caplog):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "1")
    caplog.set_level(logging.INFO, logger="app.http")

    response = client.get("/.env?token=secret", headers={"CF-Connecting-IP": "203.0.113.8"})

    assert response.status_code == 404
    records = [record for record in caplog.records if record.name == "app.http"]
    matching = [json.loads(record.getMessage()) for record in records]
    event = next(item for item in matching if item["event"] == "scanner_path_blocked")
    assert event == {
        "event": "scanner_path_blocked",
        "method": "GET",
        "status_code": 404,
        "client_ip": "203.0.113.0",
        "request_id": response.headers["x-request-id"],
    }
    assert "secret" not in records[-1].getMessage()
    assert ".env" not in records[-1].getMessage()


@pytest.mark.parametrize(
    "path",
    [
        "/.env",
        # Common wildcard probes are represented by concrete requests so the
        # middleware's HTTP response contract stays covered.
        "/.env.local.php",
        "/.env.production",
        "/.env.local",
        "/.env.*",
        "/.env.production",
        "/.env.development.local",
        "/.env.staging",
        "/.env.production.local",
        "/.env.production.bak",
        "/.env.preview.eu.local",
        "/config/.env.customer-42",
        "/.envrc",
        "/.env.example",
        "/.env.sample",
        "/.env.backup",
        "/.env.bak",
        "/vendor/.env",
        "/app/.env.production",
        "/.DS_Store",
        "/credentials",
        "/.aws/credentials",
        "/credentials.json",
        "/.ssh/id_rsa",
        "/.svn/entries",
        "/.hg/store",
        "/.git/config",
        "/.git/",
        "/.git/HEAD",
        "/.git/hooks/pre-commit",
        "/.git/objects/info/packs",
        "/.git/refs/heads/main",
        "/.git/index",
        "/.gitmodules",
        "/.gitignore",
        "/.gitconfig",
        "/%2eenv",
        "/%252eenv.production",
        "/%25252eenv",
        "/.env%3f",
        "/.env%3fanything",
        "/wp-admin%3f/setup-config.php",
        "/wp-admin;view=compact/setup-config.php",
        # Path parameters can be ignored by upstream servers when resolving
        # sensitive files, so the normalized base filename must still block.
        "/config.php;anything",
        "/composer.json;jsessionid=probe",
        "/wp-login.php;anything",
        "/backup.zip;download=1",
        "/%2525252525252525252eenv",
        "/" + "%252525" * 17 + "env",
        "/%2e%67it/config",
        "/%252e%2567it/config",
        "/.vscode/sftp.json",
        "/.idea/workspace.xml",
        "/id_rsa",
        "/home/app/.ssh/id_ed25519",
        "/home/app/.ssh/id_ecdsa",
        "/home/app/.ssh/id_dsa",
        "/.ssh/authorized_keys",
        "/.ssh/known_hosts",
        "/application.properties",
        "/application.yml",
        "/application.yaml",
        "/credentials.xml",
        "/terraform.tfstate",
        "/terraform.tfstate.backup",
        "/.npmrc",
        "/.dockercfg",
        "/.htaccess",
        "/.htpasswd",
        "/.user.ini",
        "/docker-compose.yml",
        "/docker-compose.yaml",
        "/package.json",
        "/package-lock.json",
        "/pnpm-lock.yaml",
        "/bun.lock",
        "/bun.lockb",
        "/app/pnpm-lock.yaml",
        "/app/bun.lock",
        "/yarn.lock",
        "/telescope/requests",
        "/wp-admin/setup-config.php",
        "/wp-admin/admin-post.php",
        "/wp-admin/",
        "/wp-admin/options.php",
        "/wp-admin/admin-ajax.php",
        "/wp-admin/install.php",
        "/wp-admin/admin.php",
        "/wp-admin/load-styles.php",
        "/wp-content/plugins/revslider/readme.txt",
        "/wp-includes/wlwmanifest.xml",
        "/wp-json",
        "/wp-json/wp/v2/users",
        "/wp-cron.php",
        "/wp-login.php",
        "/wp-config.php",
        "/xmlrpc.php",
        "/xmlrpc.php?rsd",
        "/xmlrpc",
        "/xmlrpc.php/",
        "/XMLRPC.PHP",
        "/phpinfo.php",
        "/php_info.php",
        "/php_info",
        "/php_info7.phtml",
        "/i.php",
        "/phpinfo.php;v=1",
        "/php_info.php;v=1",
        "/i.php;v=1",
        "/phpinfo;v=1.php",
        "/php_info;v=1.php",
        "/i;v=1.php",
        "/i.php3",
        "/phpinfo",
        "/phpinfo7.php",
        "/phpinfo7.json",
        "/phpinfo7",
        "/phpinfo7.phtml",
        "/phpinfo7.phar",
        "/phpinfo7.php5",
        "/phpinfo9.php8",
        "/phpinfo.php4",
        "/phpinfo.php9",
        "/phpinfo.php10",
        "/phpinfo.phps",
        "/phpinfo.php%00",
        "/phpinfo7.phps",
        "/PHPINFO8.PHTML",
        "/%70hpinfo%2ephp",
        "/%2570hpinfo7%252ephtml",
        "/nested/%252e%252e/phpinfo7.php",
        "/%70hpinfo",
        "/%2570hpinfo7.php",
        "/phpinfo.php/",
        "/phpinfo.php3",
        "/phpinfo.phtml",
        "/php-info.php",
        "/phpversion.php",
        "/test.phpinfo",
        "/php_info.php",
        "/php_info.php",
        "/php-info.php",
        "/php%5Finfo.php",
        "/php%2Dinfo.php",
        "/%2570hp%255Finfo%252ephp",
        "/%2570hp%252Dinfo.php",
        # Encoded aliases and extensions should remain blocked after repeated
        # decoding, just like the phpinfo variants above.
        "/php%255Finfo%252ephp",
        "/%2569%252ephp",
        "/%2525%2536%2539%252ephp",
        "/php_info",
        "/php_info7.php",
        "/php_info.phps",
        "/php_info.php9",
        "/php_info.php6",
        "/php-info.php",
        "/php-info7.php",
        "/php-info.php6",
        "/phpinf-info.php",
        "/phpinf_info.php",
        "/phpinfversion.php",
        "/info.php",
        "/test.php",
        "/PHP_INFO8.PHTML",
        "/nested/php_info7.phar",
        "/phpinf",
        "/phpinf.php",
        "/phpinf7.phtml",
        "/nested/PHPINF8.PHAR",
        "/info.php",
        "/test.php",
        "/nested/info.php",
        "/i.php",
        "/%70hpinfo.php",
        "/%2570hp_info.php",
        "/%69.php",
        "/%2569%252ephp",
        "/i",
        "/i.php3",
        "/i.php6",
        "/i.phps",
        "/i7.php",
        "/nested/I8.PHTML",
        "/i.php.bak",
        "/adminer.php",
        "/phpmyadmin/index.php",
        "/pma/index.php",
        "/server-status",
        "/server-info",
        "/cgi-bin/test.cgi",
        "/actuator/env",
        "/composer.json",
        "/backup.zip",
        "/backup.tar.gz",
        "/db.sql",
        "/dump.sql",
        "/dump.sql.gz",
        "/database.sql",
        "/config.php",
        "/config.json",
        "/config.yaml",
        "/config.yml",
        "/config.php.dist",
        "/config.php.sample",
        "/configuration.php",
        "/wp-config-sample.php",
        "/secrets.json",
        "/settings.py",
        "/local_settings.py",
        "/web.config",
        "/foo%5c.env",
        # Encoded backslashes can become separators after URL decoding.
        "/foo/%2e%2e%5c.env",
        "/foo/%252e%252e%255c.git/config",
        "/foo/%2e%2e%5cphpinfo.php",
        "/foo/%252e%252e%255ci.php",
        "/tmp/backup.zip",
        "/tmp/dump.sql.gz",
        "/private/config.php",
        "/debug/default/view",
        "/debug",
        "/trace.axd",
        "/elmah.axd",
        "/serverinfo",
        "/debugbar/open",
        "/_profiler/phpinfo",
        "/_ignition/execute-solution",
        "/console",
        "/manager/html",
        "/jenkins/login",
        "/solr/admin/info/system",
        "/owa/auth/logon.aspx",
        "/ecp/Current/exporttool",
        "/boaform/admin/formLogin",
        "/hudson",
        "/.docker/config.json",
        "/.kube/config",
        "/.terraform/terraform.tfstate",
        "/storage/logs/laravel.log",
        "/.git.bak/config",
        "/%2e%67it%2ebak/config",
        "/.git\\.bak\\config",
        "/wp-admin.old/setup-config.php",
        "/vendor.backup/.env",
        # Common path normalization and traversal probes must reach the same
        # generic 404 before any route can disclose application content.
        "/%2eenv.production",
        "/.git%2fconfig",
        "/wp-admin%2fsetup-config.php",
        # Mixed literal/encoded dots are accepted by some proxy normalizers
        # as dot segments and must not bypass the scanner path check.
        "/public/.%2e/.env",
        "/public/%2e./.git/config",
        "/public/.%2e/wp-admin/setup-config.php",
        "/public/%2e./phpinfo.php",
        "/foo/../.env",
        "/public/../.env",
        "/public/%2e%2e/.git/config",
        "/public/%252e%252e/wp-admin/setup-config.php",
        "/public/%2525252525252525252e%2525252525252525252e/.git/config",
        "/cgi-bin/%2e%2e/%2e%2e/etc/passwd",
        # Traversal markers that remain after the bounded decode passes must
        # not reach a route that an upstream with a deeper limit may resolve.
        "/public/.%252525252525252525252e/.env",
        "/public/%252525252525252525252e./wp-admin/setup-config.php",
    ],
)
def test_common_scanner_paths_are_blocked(path):
    response = client.get(path)

    assert response.status_code == 404
    assert response.text == "Not Found"
    assert response.headers["x-robots-tag"] == "noindex, nofollow"


@pytest.mark.parametrize(
    "path",
    [
        "/phpinfo.php",
        "/phpinfo.php3",
        "/phpinfo.phtml",
        "/php_info.php",
        "/php-info.php",
        "/php%5Finfo.php",
        "/php%2Dinfo.php",
        "/%2570hp%255Finfo%252ephp",
        "/%2570hp%252Dinfo.php",
        "/php_info.php3",
        "/php_info.phtml",
        "/i.php",
        "/i.php3",
        "/i.phtml",
        "/phpinfo.phps",
        "/php_info.phps",
        "/i.phps",
        "/phpinfo7.php",
        "/php_info7.php",
        "/php-info7.php",
        "/phpinf7.php",
        "/phpinfo.php5.6",
        "/php_info.php7.4",
        "/php-info7.php8.1",
        "/i.php5.6",
        "/phpinfo.php5.6.bak.old",
        "/phpinf-info.php",
        "/phpinf_info.php",
        "/phpinfversion.php",
        "/i7.php",
        "/info.php",
        "/test.php",
        "/phpinfo.php.bak.old",
        "/php_info.php.bak.old",
        "/i.php.bak.old",
        "/nested/phpinfo8.phar",
        "/nested/php_info8.phar",
        "/nested/i8.phar",
        "/foo/%2e%2e%5cphpinfo.php",
        "/foo/%252e%252e%255ci.php",
    ],
)
def test_phpinfo_scanner_aliases_return_generic_not_found(path):
    response = client.get(path, headers={"accept": "text/html"})

    assert response.status_code == 404
    assert response.text == "Not Found"
    assert "Página não encontrada" not in response.text
    assert "Traceback" not in response.text
    assert response.headers["x-robots-tag"] == "noindex, nofollow"


@pytest.mark.parametrize(
    "path",
    [
        "/.env",
        "/.env.local",
        "/.env.production",
        "/.env.production.bak",
        "/.git/config",
        "/.git/objects/info/packs",
        "/wp-admin/",
        "/wp-admin/setup-config.php",
        "/xmlrpc.php",
        "/phpinfo.php",
        "/php_info.php",
        "/i.php",
    ],
)
def test_requested_scanner_families_return_detail_free_404(path):
    response = client.get(path, headers={"accept": "text/html"})

    assert response.status_code == 404
    assert response.text == "Not Found"
    assert "Página não encontrada" not in response.text
    assert "Traceback" not in response.text
    assert response.headers["x-robots-tag"] == "noindex, nofollow"


@pytest.mark.parametrize("path", ["/phpinfo.php", "/php_info.php", "/i.php"])
def test_priority_phpinfo_probes_are_not_cached_or_disclosed(path, caplog):
    caplog.set_level(logging.INFO, logger="app.http")
    probe_query = "?token=phpinfo-probe-secret"

    response = client.get(path + probe_query, headers={"accept": "text/html"})

    assert response.status_code == 404
    assert response.text == "Not Found"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["x-robots-tag"] == "noindex, nofollow"
    assert "phpinfo-probe-secret" not in response.text
    records = [record for record in caplog.records if record.name == "app.http"]
    assert all(path not in record.getMessage() for record in records)
    assert all("phpinfo-probe-secret" not in record.getMessage() for record in records)


def test_legitimate_public_route_is_preserved():
    response = client.get("/robots.txt")

    assert response.status_code == 200
    assert "User-agent: *" in response.text


@pytest.mark.parametrize("path", [
    "/static/../.env",
    "/static/css/../../.git/config",
    "/static/css/../../wp-admin/setup-config.php",
    "/static/css/../../phpinfo.php",
])
def test_scanner_paths_cannot_escape_static_mount(path):
    response = client.get(path)

    assert response.status_code == 404
    assert response.text == "Not Found"
    assert response.headers["x-robots-tag"] == "noindex, nofollow"


def test_legitimate_static_asset_with_dot_segment_is_preserved():
    response = client.get("/static/css/./style.css")

    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]


def test_phpinfo_path_with_literal_nul_is_blocked_by_filter():
    assert is_sensitive_scanner_path("/phpinfo.php\x00ignored") is True


@pytest.mark.parametrize(
    "path",
    [
        "/.htaccess.bak",
        "/.htpasswd.old",
        "/.user.ini.orig",
        "/package.json.bak.old",
        "/package-lock.json.backup.tmp",
        "/web.config.save",
        "/backup.tar.gz.swp",
        "/backup.zip~",
        "/credentials.tmp",
        "/credentials.json.backup",
        "/secrets.json~",
        "/settings.py.tmp",
        "/pnpm-lock.yaml.bak",
        "/bun.lock.old",
        "/bun.lockb~",
        "/local_settings.py.backup",
        "/.env~",
        "/.envrc.tmp",
        "/dump.sql.gz.bak",
        "/private/config.php.old",
        "/.git/config.bak",
        "/.env.production.bak.old",
        "/.git.bak.old/config",
        "/nested/.ssh.orig.backup/id_rsa",
        "/.gitmodules.bak",
        "/.gitignore.bak.old",
        "/.ssh/id_rsa.old",
        "/.svn/entries~",
        "/.hg/store.orig",
        "/docker-compose.yml.orig",
        "/wp-login.php.backup",
        "/wp-config.php.bak",
        "/xmlrpc.php.old",
        "/info.php.bak",
        "/test.php.old",
        "/phpinfo.php.bak",
        "/phpinfo.php.bak.old",
        "/phpinfo7.phtml.old.backup",
        "/phpinfo.phtml.old",
        "/php_info.php.bak",
        "/php_info.php.bak.old",
        "/php_info7.phtml.old",
        "/i.php.old",
        "/i.php.bak.old",
        "/config.php.dist.bak",
        "/wp-config-sample.php~",
    ],
)
def test_sensitive_scanner_backup_variants_are_blocked(path):
    response = client.get(path)

    assert response.status_code == 404
    assert response.text == "Not Found"
    assert response.headers["x-robots-tag"] == "noindex, nofollow"


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/parceiros",
        "/eventos",
        "/contato",
        "/privacidade",
        "/cadastro",
        "/eventos.old",
        "/parceiros.bak",
        "/contato.orig",
        "/privacidade.save",
        "/eventos.tmp",
        "/parceiros.backup",
        "/contato~",
        "/user.php",
        "/myphpinfo.php",
        "/phpinfo-api",
        "/phpinfo-report.php",
        "/application-guide.yml",
        "/credentials-help.xml",
        "/terraform.tfstate.example",
        "/ssh/authorized_keys-guide",
        "/phpinfo7.txt",
        "/php_info-report.php",
        "/php_info-report.php",
        "/php-info-api.php",
        "/php_info7.txt",
        "/i.txt",
        "/i-api.php",
        "/info-api.php",
        "/test-report.php",
        "/phpinf-api.php",
        "/php_info-report.php",
        "/lockfile",
        "/my-pnpm-lock.yaml",
        "/bun-lock.yaml",
        "/phpinfo-report.php",
        "/parceiros.bak",
        "/eventos.old",
        "/contato.backup",
        "/public/../eventos",
        "/public/%2e%2e/contato",
        "/public/.%2e/contato",
        "/public/%2e./eventos",
        # Deep encoding of ordinary route characters remains routable.
        "/eventos%252525252525252525252f",
        "/parceiros;view=compact",
        "/.env-file.bak.old",
        "/.github.bak.old",
        "/package-help.json.bak.old",
    ],
)
def test_legitimate_public_paths_are_not_blocked_by_scanner_filter(path):
    assert is_sensitive_scanner_path(path) is False

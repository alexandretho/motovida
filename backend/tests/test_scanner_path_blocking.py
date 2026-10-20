import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402
from app.security import is_sensitive_scanner_path  # noqa: E402


client = TestClient(app)


@pytest.mark.parametrize(
    "path",
    [
        "/.env",
        "/.env.local",
        "/.env.*",
        "/.env.production",
        "/.env.development.local",
        "/.envrc",
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
        "/.git/HEAD",
        "/.git/objects/info/packs",
        "/%2eenv",
        "/%252eenv.production",
        "/%25252eenv",
        "/%2e%67it/config",
        "/%252e%2567it/config",
        "/.vscode/sftp.json",
        "/.idea/workspace.xml",
        "/id_rsa",
        "/.npmrc",
        "/.dockercfg",
        "/.htaccess",
        "/.htpasswd",
        "/.user.ini",
        "/docker-compose.yml",
        "/docker-compose.yaml",
        "/package.json",
        "/package-lock.json",
        "/yarn.lock",
        "/telescope/requests",
        "/wp-admin/setup-config.php",
        "/wp-admin/",
        "/wp-admin/admin-ajax.php",
        "/wp-admin/install.php",
        "/wp-content/plugins/revslider/readme.txt",
        "/wp-includes/wlwmanifest.xml",
        "/wp-json",
        "/wp-json/wp/v2/users",
        "/wp-cron.php",
        "/wp-login.php",
        "/wp-config.php",
        "/xmlrpc.php",
        "/xmlrpc.php?rsd",
        "/phpinfo.php",
        "/phpinfo",
        "/phpinfo7.php",
        "/phpinfo7",
        "/%70hpinfo",
        "/%2570hpinfo7.php",
        "/phpinfo.php/",
        "/phpinfo.php3",
        "/phpinfo.phtml",
        "/php-info.php",
        "/phpversion.php",
        "/test.phpinfo",
        "/php_info.php",
        "/info.php",
        "/test.php",
        "/nested/info.php",
        "/i.php",
        "/%70hpinfo.php",
        "/%2570hp_info.php",
        "/%69.php",
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
        "/tmp/backup.zip",
        "/tmp/dump.sql.gz",
        "/private/config.php",
        "/debug/default/view",
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
        "/foo/../.env",
    ],
)
def test_common_scanner_paths_are_blocked(path):
    response = client.get(path)

    assert response.status_code == 404
    assert response.text == "Not Found"
    assert response.headers["x-robots-tag"] == "noindex, nofollow"


def test_legitimate_public_route_is_preserved():
    response = client.get("/robots.txt")

    assert response.status_code == 200
    assert "User-agent: *" in response.text


@pytest.mark.parametrize(
    "path",
    [
        "/.htaccess.bak",
        "/.htpasswd.old",
        "/.user.ini.orig",
        "/web.config.save",
        "/backup.tar.gz.swp",
        "/backup.zip~",
        "/credentials.tmp",
        "/credentials.json.backup",
        "/secrets.json~",
        "/settings.py.tmp",
        "/local_settings.py.backup",
        "/.env~",
        "/.envrc.tmp",
        "/dump.sql.gz.bak",
        "/private/config.php.old",
        "/.git/config.bak",
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
        "/phpinfo.phtml.old",
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
        "/parceiros.bak",
        "/eventos.old",
        "/contato.backup",
    ],
)
def test_legitimate_public_paths_are_not_blocked_by_scanner_filter(path):
    assert is_sensitive_scanner_path(path) is False

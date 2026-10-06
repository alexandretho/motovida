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
        "/vendor/.env",
        "/app/.env.production",
        "/.aws/credentials",
        "/.ssh/id_rsa",
        "/.svn/entries",
        "/.hg/store",
        "/.git/config",
        "/wp-admin/setup-config.php",
        "/wp-content/plugins/revslider/readme.txt",
        "/wp-includes/wlwmanifest.xml",
        "/wp-login.php",
        "/xmlrpc.php",
        "/phpinfo.php",
        "/php_info.php",
        "/i.php",
        "/server-status",
        "/server-info",
        "/cgi-bin/test.cgi",
        "/actuator/env",
        "/composer.json",
        "/debug/default/view",
    ],
)
def test_common_scanner_paths_are_blocked(path):
    response = client.get(path)

    assert response.status_code == 404
    assert response.text == "Not Found"


def test_legitimate_public_route_is_preserved():
    response = client.get("/robots.txt")

    assert response.status_code == 200
    assert "User-agent: *" in response.text


@pytest.mark.parametrize(
    "path",
    ["/", "/parceiros", "/eventos", "/contato", "/privacidade", "/cadastro"],
)
def test_legitimate_public_paths_are_not_blocked_by_scanner_filter(path):
    assert is_sensitive_scanner_path(path) is False

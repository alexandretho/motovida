import os
import re
import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app import ratelimit  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import public  # noqa: E402


def setup_function():
    ratelimit.clear()


def test_blocks_after_limit_and_resets_after_window():
    for i in range(3):
        assert ratelimit.hit("contato", "1.1.1.1", 3, 60, now=float(i)) is False
    assert ratelimit.hit("contato", "1.1.1.1", 3, 60, now=5.0) is True
    assert ratelimit.hit("contato", "1.1.1.1", 3, 60, now=100.0) is False


def test_scoped_by_ip_and_scope():
    for i in range(3):
        ratelimit.hit("contato", "1.1.1.1", 3, 60, now=float(i))
    assert ratelimit.hit("contato", "2.2.2.2", 3, 60, now=4.0) is False
    assert ratelimit.hit("cadastro", "1.1.1.1", 3, 60, now=4.0) is False


def test_rate_limit_key_store_stays_bounded_and_evicts_oldest():
    original_capacity = ratelimit.MAX_RATE_LIMIT_KEYS
    ratelimit.MAX_RATE_LIMIT_KEYS = 2
    try:
        assert ratelimit.hit("contato", "1.1.1.1", 2, 60, now=1.0) is False
        assert ratelimit.hit("contato", "2.2.2.2", 2, 60, now=2.0) is False
        assert ratelimit.hit("contato", "3.3.3.3", 2, 60, now=3.0) is False

        assert len(ratelimit._hits) == 2
        assert ("contato", "1.1.1.1") not in ratelimit._hits
        assert ("contato", "2.2.2.2") in ratelimit._hits
        assert ("contato", "3.3.3.3") in ratelimit._hits
    finally:
        ratelimit.MAX_RATE_LIMIT_KEYS = original_capacity


def csrf_token_from(response) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
    assert match is not None
    return match.group(1)


def invalid_registration_payload(csrf_token: str) -> dict[str, str]:
    return {
        "csrf_token": csrf_token,
        "full_name": "A",
        "cpf": "00000000000",
        "phone": "41999999999",
        "whatsapp": "41999999999",
        "email": "invalido",
        "city": "Curitiba",
        "state": "PR",
        "profession": "motoboy",
        "mei_status": "nao_possui",
        "support_needs": "",
        "password": "123",
        "lgpd_accept": "on",
    }


def test_registration_route_rate_limits_with_flash_and_valid_csrf():
    client = TestClient(app)
    csrf_token = csrf_token_from(client.get("/cadastro"))

    payload = invalid_registration_payload(csrf_token)
    for _ in range(public.REGISTER_RATE_LIMIT):
        response = client.post("/cadastro", data=payload, follow_redirects=False)
        assert response.status_code == 400

    response = client.post("/cadastro", data=payload, follow_redirects=True)

    assert response.status_code == 200
    assert public.REGISTER_RATE_LIMIT_MESSAGE in response.text
    assert "Token CSRF inválido" not in response.text

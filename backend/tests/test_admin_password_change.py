import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app.routers.admin import validate_admin_password_change  # noqa: E402
from app.security import hash_password  # noqa: E402


def test_validate_admin_password_change_accepts_valid_change():
    stored_hash = hash_password("dev-only-change-me")

    errors = validate_admin_password_change("dev-only-change-me", "nova-senha-123", "nova-senha-123", stored_hash)

    assert errors == []


def test_validate_admin_password_change_rejects_wrong_current_password():
    stored_hash = hash_password("dev-only-change-me")

    errors = validate_admin_password_change("errada", "nova-senha-123", "nova-senha-123", stored_hash)

    assert "Senha atual incorreta." in errors


def test_validate_admin_password_change_rejects_weak_or_mismatched_password():
    stored_hash = hash_password("dev-only-change-me")

    errors = validate_admin_password_change("dev-only-change-me", "curta", "diferente", stored_hash)

    assert "A nova senha deve ter pelo menos 8 caracteres." in errors
    assert "A confirmação da nova senha não confere." in errors


def test_validate_admin_password_change_rejects_same_password():
    stored_hash = hash_password("dev-only-change-me")

    errors = validate_admin_password_change("dev-only-change-me", "dev-only-change-me", "dev-only-change-me", stored_hash)

    assert "Escolha uma senha diferente da atual." in errors

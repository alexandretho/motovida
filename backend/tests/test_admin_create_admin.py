import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app.routers.admin import validate_new_admin  # noqa: E402


def test_valid_new_admin():
    assert validate_new_admin("novo@motovida.org.br", "senha-forte-1", "senha-forte-1", False) == []


def test_rejects_duplicate_email():
    assert "Já existe um usuário com este e-mail." in validate_new_admin("a@b.com", "senha-forte-1", "senha-forte-1", True)


def test_rejects_invalid_email_short_and_mismatched_password():
    errors = validate_new_admin("invalido", "curta", "outra", False)
    assert "E-mail inválido." in errors
    assert "A senha deve ter pelo menos 8 caracteres." in errors
    assert "A confirmação da senha não confere." in errors

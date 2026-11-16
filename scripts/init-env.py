#!/usr/bin/env python3
"""Gera .env local com credenciais aleatórias sem sobrescrever arquivos existentes."""
import os
import secrets
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
example = os.path.join(root, ".env.example")
target = os.path.join(root, ".env")

if os.path.exists(target):
    print("Erro: .env já existe; não foi alterado. Faça backup e edite manualmente se necessário.", file=sys.stderr)
    raise SystemExit(1)
if not os.path.isfile(example):
    print("Erro: .env.example não encontrado.", file=sys.stderr)
    raise SystemExit(1)

values = {
    "MYSQL_ROOT_PASSWORD": secrets.token_urlsafe(36),
    "MYSQL_PASSWORD": secrets.token_urlsafe(36),
    "SECRET_KEY": secrets.token_urlsafe(48),
    "ADMIN_PASSWORD": secrets.token_urlsafe(24),
}
with open(example, encoding="utf-8") as source:
    template = source.read()
lines = []
for line in template.splitlines():
    if "=" in line and not line.lstrip().startswith("#"):
        key, value = line.split("=", 1)
        if key in values:
            line = f"{key}={values[key]}"
    lines.append(line)

fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
except Exception:
    try:
        os.unlink(target)
    except OSError:
        pass
    raise
print(".env criado com credenciais aleatórias e permissões 600.")
print("Edite ADMIN_EMAIL, SITE_URL e demais opções antes de publicar o serviço.")

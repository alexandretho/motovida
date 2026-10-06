import os


def env_flag(name: str, default: str = "0") -> bool:
    """Converte flags de ambiente comuns para booleano."""
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on", "sim"}


DB_USER = os.getenv("MYSQL_USER", "motovida")
DB_PASSWORD = os.getenv("MYSQL_PASSWORD", "gere-uma-senha-forte-para-o-banco")
DB_HOST = os.getenv("MYSQL_HOST", "mysql")
DB_PORT = os.getenv("MYSQL_PORT", "3306")
DB_NAME = os.getenv("MYSQL_DATABASE", "motovida")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
SESSION_COOKIE_SECURE = env_flag("SESSION_COOKIE_SECURE")

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.invalid")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "dev-only-change-me")

POLICY_VERSION = "1.0"

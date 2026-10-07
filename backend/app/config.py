import os


DEFAULT_SITE_URL = "https://motovida.syntratech.com.br"
DEFAULT_GA_MEASUREMENT_ID = "G-VHCJDB0QNS"


def env_flag(name: str, default: str = "0") -> bool:
    """Converte flags de ambiente comuns para booleano."""
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on", "sim"}


def env_text(name: str, default: str) -> str:
    """Lê texto de ambiente, ignorando valores vazios/acidentais."""
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def normalize_site_url(value: str) -> str:
    """Remove barra final para gerar links absolutos consistentes."""
    return value.strip().rstrip("/") or DEFAULT_SITE_URL


DB_USER = os.getenv("MYSQL_USER", "motovida")
DB_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
DB_HOST = os.getenv("MYSQL_HOST", "mysql")
DB_PORT = os.getenv("MYSQL_PORT", "3306")
DB_NAME = os.getenv("MYSQL_DATABASE", "motovida")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
SESSION_COOKIE_SECURE = env_flag("SESSION_COOKIE_SECURE")

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.invalid")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "dev-only-change-me")

SITE_URL = normalize_site_url(env_text("SITE_URL", DEFAULT_SITE_URL))
GA_MEASUREMENT_ID = env_text("GA_MEASUREMENT_ID", DEFAULT_GA_MEASUREMENT_ID)

POLICY_VERSION = "1.0"

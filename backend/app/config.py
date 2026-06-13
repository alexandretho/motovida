import os

DB_USER = os.getenv("MYSQL_USER", "motovida")
DB_PASSWORD = os.getenv("MYSQL_PASSWORD", "motovida123")
DB_HOST = os.getenv("MYSQL_HOST", "mysql")
DB_PORT = os.getenv("MYSQL_PORT", "3306")
DB_NAME = os.getenv("MYSQL_DATABASE", "motovida")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

SECRET_KEY = os.getenv("SECRET_KEY", "troque-esta-chave-em-producao")

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@motovida.org.br")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

POLICY_VERSION = "1.0"

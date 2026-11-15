import logging
import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from app import models  # noqa: E402
from app.config import render_alembic_database_url  # noqa: E402
from app.migrations import _config, migrate_database  # noqa: E402


def test_migration_does_not_disable_application_loggers(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'logger.db'}")
    app_logger = logging.getLogger("app.http")
    previous_disabled = app_logger.disabled
    app_logger.disabled = False
    try:
        migrate_database(engine)
        assert app_logger.disabled is False
    finally:
        app_logger.disabled = previous_disabled


def test_baseline_downgrade_refuses_to_drop_schema(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'no-drop.db'}")
    migrate_database(engine)

    with engine.connect() as connection:
        with pytest.raises(RuntimeError, match="não pode ser revertida"):
            command.downgrade(_config(connection), "base")
        assert "users" in inspect(connection).get_table_names()


def test_migrate_empty_database_creates_current_schema_and_version(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")

    migrate_database(engine)
    migrate_database(engine)

    inspector = inspect(engine)
    assert set(models.Base.metadata.tables).issubset(set(inspector.get_table_names()))
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "e0c9e33e18c5"


def test_adopts_existing_schema_and_preserves_rows(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    models.Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO users (email, password_hash, role, created_at) VALUES (:email, :hash, :role, :created)"),
            {"email": "existing@example.test", "hash": "hash", "role": "admin", "created": "2026-01-01 00:00:00"},
        )

    migrate_database(engine)

    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM users WHERE email='existing@example.test'")) == 1
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "e0c9e33e18c5"


def test_incomplete_legacy_schema_fails_without_stamping(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'partial.db'}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))

    with pytest.raises(RuntimeError, match="incompleto"):
        migrate_database(engine)

    assert "alembic_version" not in inspect(engine).get_table_names()


def test_alembic_url_keeps_reserved_characters_in_password():
    from sqlalchemy.engine import URL, make_url

    password = "p@ss:/word%chars"
    url = URL.create("mysql+pymysql", username="user", password=password, host="localhost", database="db")
    config = Config()
    config.set_main_option("sqlalchemy.url", render_alembic_database_url(url))

    assert make_url(config.get_main_option("sqlalchemy.url")).password == password

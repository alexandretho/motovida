from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from . import models

BACKEND_DIR = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"


def _config(connection) -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.attributes["connection"] = connection
    return config


def _validate_existing_schema(connection) -> None:
    inspector = inspect(connection)
    actual_tables = set(inspector.get_table_names()) - {"alembic_version"}
    expected_tables = set(models.Base.metadata.tables)
    missing_tables = expected_tables - actual_tables
    missing_columns = {
        f"{table}.{column.name}"
        for table in expected_tables & actual_tables
        for column in models.Base.metadata.tables[table].columns
        if column.name not in {item["name"] for item in inspector.get_columns(table)}
    }
    if missing_tables or missing_columns:
        details = []
        if missing_tables:
            details.append("tabelas: " + ", ".join(sorted(missing_tables)))
        if missing_columns:
            details.append("colunas: " + ", ".join(sorted(missing_columns)))
        raise RuntimeError(
            "Esquema legado incompleto; migração automática interrompida para evitar perda/erro: "
            + "; ".join(details)
        )


def migrate_database(engine) -> None:
    """Aplica migrações; adota sem DDL bancos legados com esquema completo."""
    with engine.begin() as connection:
        tables = set(inspect(connection).get_table_names())
        config = _config(connection)
        if "alembic_version" not in tables:
            app_tables = tables - {"alembic_version"}
            if app_tables:
                _validate_existing_schema(connection)
                command.stamp(config, "head")
            else:
                command.upgrade(config, "head")
        else:
            command.upgrade(config, "head")

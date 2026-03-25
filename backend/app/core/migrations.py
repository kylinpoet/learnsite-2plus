from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from .database import get_database_url


def upgrade_database_schema() -> None:
    backend_dir = Path(__file__).resolve().parents[2]
    alembic_ini = backend_dir / "alembic.ini"
    alembic_dir = backend_dir / "alembic"

    config = Config(str(alembic_ini))
    config.set_main_option("script_location", str(alembic_dir))
    config.set_main_option("sqlalchemy.url", get_database_url())
    config.set_main_option("prepend_sys_path", str(backend_dir))
    command.upgrade(config, "head")

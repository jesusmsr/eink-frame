"""Aplica las migraciones de Alembic al arrancar."""
from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def alembic_config(db_path: Path) -> AlembicConfig:
    cfg = AlembicConfig()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def upgrade(db_path: Path) -> None:
    command.upgrade(alembic_config(db_path), "head")

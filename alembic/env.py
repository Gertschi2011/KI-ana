from __future__ import annotations
import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- Project imports --------------------------------------------------------
# Ensure we can import netapi.*
try:
    KI_ROOT = os.getenv("KI_ROOT")
    if KI_ROOT:
        sys.path.insert(0, KI_ROOT)
    else:
        # Fallback to home ~/ki_ana
        from pathlib import Path
        sys.path.insert(0, str(Path.home() / "ki_ana"))
except Exception:
    pass

# Import Base and models to populate metadata
try:
    from netapi.db import Base  # type: ignore
    from netapi import models  # noqa: F401  # register models
    target_metadata = Base.metadata
except Exception as e:  # pragma: no cover
    target_metadata = None

# Database URL: prefer DATABASE_URL from environment (CI/dev override).
# Fall back to a local sqlite file if project helpers cannot be imported.
db_url = (os.getenv("DATABASE_URL") or "").strip()
if not db_url:
    try:
        from netapi.db import _default_sqlite_url  # type: ignore

        db_url = str(_default_sqlite_url() or "").strip()
    except Exception:
        db_url = "sqlite:///./db.sqlite3"

if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

# other values from the config, defined by the needs of env.py, can be
# acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # NOTE: Widening alembic_version.version_num is handled in-order via
        # a dedicated migration (0012a_alembic_ver_255). Avoid doing DDL here.

        # Fresh-DB baseline: many early migrations were originally SQLite-only.
        # Do NOT call SQLAlchemy create_all() here.
        # We rely on Alembic migrations to create/alter schema in-order.
        # (create_all() can create "future" columns/tables and break later migrations.)

        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

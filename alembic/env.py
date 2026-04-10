"""Alembic migration environment configuration."""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url from environment variable if set
db_url = os.environ.get("DATABASE_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)
else:
    # Resolve %(PG_PASSWORD)s placeholder from env
    pg_password = os.environ.get("PG_PASSWORD", "changeme")
    raw_url = config.get_main_option("sqlalchemy.url") or ""
    config.set_main_option("sqlalchemy.url", raw_url.replace("%(PG_PASSWORD)s", pg_password))


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL to stdout)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=None, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connect to database)."""
    connectable = create_engine(config.get_main_option("sqlalchemy.url", ""))
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

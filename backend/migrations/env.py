"""Alembic environment (action plan P01).

The database URL comes from the same `Settings` the API uses, never from alembic.ini, so
a migration cannot be pointed at a different database than the one the service reads. No
credential is written to a tracked file.
"""
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import Base  # noqa: E402
from app.settings import Settings  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def database_url():
    """The URL the caller passed, else the application's own settings.

    It travels through `config.attributes` rather than the ini file so a '%' in the URL is
    never treated as ConfigParser interpolation.
    """
    return config.attributes.get('database_url') or Settings.from_env().database_url


def run_migrations_offline():
    context.configure(url=database_url(), target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={'paramstyle': 'named'}, render_as_batch=True,
                      compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    section = config.get_section(config.config_ini_section, {})
    section['sqlalchemy.url'] = database_url()
    connectable = config.attributes.get('connection', None)
    if connectable is None:
        connectable = engine_from_config(section, prefix='sqlalchemy.', poolclass=pool.NullPool)
        with connectable.connect() as connection:
            _run(connection)
        connectable.dispose()
    else:
        _run(connectable)


def _run(connection):
    # render_as_batch keeps future ALTERs workable on SQLite, which the pilot still supports.
    context.configure(connection=connection, target_metadata=target_metadata,
                      render_as_batch=connection.dialect.name == 'sqlite', compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

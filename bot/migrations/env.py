import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Allow runtime / CI to override the DB URL via environment variable.
# Resolution order:
#   1. BOT_DATABASE_URL env var (explicit override — used in production and CI)
#   2. Constructed from individual BOT_DB_* env vars (matches how the app builds it)
#   3. sqlalchemy.url from alembic.ini (local dev default)
_env_url = os.environ.get("BOT_DATABASE_URL")
if not _env_url:
    _host = os.environ.get("BOT_DB_HOST")
    _port = os.environ.get("BOT_DB_PORT")
    _name = os.environ.get("BOT_DB_NAME") or os.environ.get("POSTGRES_DB")
    _user = os.environ.get("BOT_DB_USER") or os.environ.get("POSTGRES_USER")
    _pass = os.environ.get("BOT_DB_PASSWORD") or os.environ.get("POSTGRES_PASSWORD")
    if _host and _port and _name and _user:
        _env_url = f"postgresql+psycopg2://{_user}:{_pass or ''}@{_host}:{_port}/{_name}"
if _env_url:
    config.set_main_option("sqlalchemy.url", _env_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
from internal.domain import Base

target_metadata = Base.metadata


# other values from the config, defined by the needs of env.py,
# can be acquired:
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
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

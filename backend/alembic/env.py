from logging.config import fileConfig

from sqlalchemy import make_url, pool

from alembic import context
from app.config import settings
from sqlalchemy import create_engine

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app.models

target_metadata = app.models.base.Base.metadata

# 数据库连接URL
# 可选参数 -x target=test / -x target=main 使用test数据库或主数据库
x_args = context.get_x_argument(as_dictionary=True)
target = x_args.get("target") or "main"  # 默认使用主数据库
if target not in {"main", "test"}:
    raise ValueError(f"unknown alembic target: {target!r}, expected 'main' or 'test'")

if target == "test":
    if not settings.test_database_url:
        raise ValueError("TEST_DATABASE_URL is required when target=test")
    target_database_url = settings.test_database_url
else:
    target_database_url = settings.database_url

print(
    f"[alembic] target={target} database={make_url(target_database_url).database}",
    file=sys.stderr,
)


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
    context.configure(
        url=target_database_url,
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
    connectable = create_engine(target_database_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

"""
alembic/env.py

Customized to load DATABASE_URL from app.core.config (single source
of truth, same .env the app itself reads) and to point autogenerate
at our SQLAlchemy Base.metadata.
"""

import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

# Make "app" importable when alembic is run from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.infrastructure.db.session import Base
from app.infrastructure.db import models  # noqa: F401  (populates Base.metadata)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Built directly from our app settings instead of alembic.ini's
    # [alembic] section, to avoid any mismatch between the two.
    connectable = create_engine(settings.DATABASE_URL, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
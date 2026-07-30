"""
app/infrastructure/db/session.py

SQLAlchemy engine + session factory. PostgreSQL only (no SQLite
fallback here - this platform is designed for production Postgres
from day one, unlike a prototype).
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    future=True,
)

Base = declarative_base()


def get_db() -> Generator:
    """
    FastAPI dependency that yields a DB session and always closes it,
    even if an exception is raised mid-request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
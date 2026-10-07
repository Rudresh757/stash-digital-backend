"""SQLAlchemy engine/session set up for Neon serverless Postgres."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    get_settings().database_url,
    pool_pre_ping=True,   # test connections before use: survives Neon idle drops / cold starts
    pool_recycle=300,     # recycle connections every 5 minutes
    pool_size=5,
    max_overflow=5,
    pool_timeout=30,
    connect_args={"connect_timeout": 10},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables on startup (no Alembic for now)."""
    from app import models  # noqa: F401  (registers the models on Base.metadata)

    Base.metadata.create_all(bind=engine)
"""SQLAlchemy engine/session wiring.

`create_engine` does not open a connection — SQLAlchemy connects lazily on
first use, so importing this module (and therefore `app.main`) still causes
zero network I/O, consistent with the existing Phase 1E contract.
"""

from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine():
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    return create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a request-scoped SQLAlchemy session."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()

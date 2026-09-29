"""Deterministic, offline auth test fixtures.

Uses an in-memory SQLite database per test (via SQLAlchemy's generic types,
the same models.py that targets Postgres in production works here
unchanged) — no real Postgres connection needed for the deterministic
suite, and zero Google network calls (see test_google.py, which mocks
app.auth.service.verify_google_credential directly).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import models as _auth_models  # noqa: F401 - registers tables on Base.metadata
from app.db import Base, get_db_session
from app.main import app


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine) -> Session:
    session_factory = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def client(db_engine):
    session_factory = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)

    def _override_get_db_session():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = _override_get_db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db_session, None)

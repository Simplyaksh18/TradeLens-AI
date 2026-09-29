"""Deployment-configuration tests: DATABASE_URL driver normalization
(see CLAUDE.md deployment-compatibility notes). No network, no real
database connection -- only the string transformation is tested."""

from __future__ import annotations

from app.core.config import _normalize_database_url


def test_bare_postgres_scheme_is_rewritten_to_the_installed_psycopg_driver():
    assert (
        _normalize_database_url("postgres://user:pass@host.render.com/dbname")
        == "postgresql+psycopg://user:pass@host.render.com/dbname"
    )


def test_bare_postgresql_scheme_is_rewritten_to_the_installed_psycopg_driver():
    assert (
        _normalize_database_url("postgresql://user:pass@host.render.com/dbname")
        == "postgresql+psycopg://user:pass@host.render.com/dbname"
    )


def test_already_explicit_psycopg_driver_scheme_is_left_unchanged():
    url = "postgresql+psycopg://user:pass@host/dbname"
    assert _normalize_database_url(url) == url


def test_sqlite_url_is_left_unchanged():
    url = "sqlite:///./tradelens_dev.db"
    assert _normalize_database_url(url) == url


def test_query_string_and_credentials_are_preserved_verbatim():
    url = "postgres://user:p%40ss@host.render.com:5432/dbname?sslmode=require"
    assert _normalize_database_url(url) == "postgresql+psycopg://user:p%40ss@host.render.com:5432/dbname?sslmode=require"

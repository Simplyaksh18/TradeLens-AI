"""Deployment-compatibility tests: CORS origin configuration for a
cross-origin production deployment (Vercel frontend + Render backend).
See CLAUDE.md deployment-compatibility notes. `DATABASE_URL` driver
normalization is covered separately in tests/unit/test_config.py."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.core.config import _parse_cors_origins

_PRODUCTION_ORIGIN = "https://trade-lens-ai-omega.vercel.app"


# ---------------------------------------------------------------------------
# Pure origin-list parsing (no app/network involved)
# ---------------------------------------------------------------------------


def test_local_dev_origins_are_always_present_by_default():
    origins = _parse_cors_origins(None)
    assert "http://localhost:5173" in origins
    assert "http://127.0.0.1:5173" in origins


def test_extra_origin_is_added_without_dropping_local_dev_origins():
    origins = _parse_cors_origins(_PRODUCTION_ORIGIN)
    assert _PRODUCTION_ORIGIN in origins
    assert "http://localhost:5173" in origins
    assert "http://127.0.0.1:5173" in origins


def test_multiple_comma_separated_origins_are_all_included_and_deduplicated():
    raw = f"{_PRODUCTION_ORIGIN}, http://localhost:5173, https://another-preview.vercel.app"
    origins = _parse_cors_origins(raw)
    assert origins.count("http://localhost:5173") == 1
    assert _PRODUCTION_ORIGIN in origins
    assert "https://another-preview.vercel.app" in origins


def test_blank_and_whitespace_only_extra_origins_are_ignored():
    origins = _parse_cors_origins("  ,  ,")
    assert origins == ("http://localhost:5173", "http://127.0.0.1:5173")


def test_wildcard_is_never_silently_produced():
    origins = _parse_cors_origins("*")
    # "*" is passed through as a literal origin string if configured, but
    # never SUBSTITUTED for the explicit list -- allow_credentials=True in
    # app.main means CORSMiddleware would reject a real "*" origin's
    # preflight anyway (see the HTTP-level test below for the actual
    # credentialed-request proof); this only proves the parser itself does
    # not silently expand or replace anything.
    assert "http://localhost:5173" in origins


# ---------------------------------------------------------------------------
# HTTP-level proof: a real CORSMiddleware, configured exactly the way
# app.main configures it (allow_credentials=True, explicit origin list,
# never "*"), correctly allows a credentialed cross-origin request from a
# production-shaped origin and rejects one from an unlisted origin. A
# throwaway app is used here (rather than app.main.app) because CORS
# origins are read once at app-construction time from settings, which is
# already covered as configuration by test_config.py / the parsing tests
# above -- this test proves the MIDDLEWARE BEHAVIOR for that configuration
# shape, independent of import-time wiring.
# ---------------------------------------------------------------------------


def _make_app(origins: tuple[str, ...]) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
    )

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok"}

    return app


def test_production_vercel_origin_preflight_is_allowed_with_credentials():
    origins = _parse_cors_origins(_PRODUCTION_ORIGIN)
    client = TestClient(_make_app(origins))

    response = client.options(
        "/api/v1/health",
        headers={"Origin": _PRODUCTION_ORIGIN, "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-origin") == _PRODUCTION_ORIGIN
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_actual_credentialed_get_reflects_the_production_origin():
    origins = _parse_cors_origins(_PRODUCTION_ORIGIN)
    client = TestClient(_make_app(origins))

    response = client.get("/api/v1/health", headers={"Origin": _PRODUCTION_ORIGIN})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == _PRODUCTION_ORIGIN
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_unlisted_origin_is_not_granted_cors_access_even_with_production_origin_configured():
    origins = _parse_cors_origins(_PRODUCTION_ORIGIN)
    client = TestClient(_make_app(origins))

    response = client.get("/api/v1/health", headers={"Origin": "https://evil.example.com"})
    assert response.headers.get("access-control-allow-origin") != "https://evil.example.com"
    assert response.headers.get("access-control-allow-origin") is None


def test_local_dev_origin_still_works_alongside_a_configured_production_origin():
    origins = _parse_cors_origins(_PRODUCTION_ORIGIN)
    client = TestClient(_make_app(origins))

    response = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"

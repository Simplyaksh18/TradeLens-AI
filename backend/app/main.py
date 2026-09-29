"""TradeLens API entry point.

Run with: uvicorn app.main:app --reload

Importing this module (or wrapping `app` in a TestClient) must never touch
the network or the filesystem — no NSE refresh, no Yahoo call, no cache
warm-up, no DB connection happens here. All dependencies (see
app.api.dependencies, app.db) are constructed lazily on first use inside a
request.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_exception_handlers
from app.api.routes import (
    analytics,
    audits,
    auth,
    backtests,
    health,
    indicators,
    instruments,
    investigations,
    market_data,
    outcomes,
    research,
    strategies,
)
from app.core.config import settings

app = FastAPI(
    title="TradeLens API",
    version="0.1.0",
    description="Explainable algorithmic-trading strategy research and auditing API (research/education only).",
)

# Phase 1G note: authentication now uses an HttpOnly session cookie, so
# CORS must allow credentials — and per the CORS spec, allow_credentials=True
# can NEVER be combined with a wildcard origin. Only explicit origins are
# allowed: the local-dev origins below plus any deployment-specific origin
# from CORS_ALLOWED_ORIGINS (see app.core.config._parse_cors_origins), never
# "*". For the session cookie to actually be sent cross-port in local dev,
# frontend and backend must share the same HOSTNAME (both "localhost") —
# "localhost" and "127.0.0.1" are different hosts for same-site cookie
# purposes even though both are loopback, so the 127.0.0.1 origin below is
# CORS-allowed but will NOT receive a working session cookie. See CLAUDE.md
# Phase 1G for the full review.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_allowed_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)

register_exception_handlers(app)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(instruments.router, prefix="/api/v1", tags=["instruments"])
app.include_router(market_data.router, prefix="/api/v1", tags=["market-data"])
app.include_router(indicators.router, prefix="/api/v1", tags=["indicators"])
app.include_router(strategies.router, prefix="/api/v1", tags=["strategies"])
app.include_router(outcomes.router, prefix="/api/v1", tags=["outcomes"])
app.include_router(backtests.router, prefix="/api/v1", tags=["backtests"])
app.include_router(analytics.router, prefix="/api/v1", tags=["analytics"])
app.include_router(audits.router, prefix="/api/v1", tags=["audits"])
app.include_router(investigations.router, prefix="/api/v1", tags=["investigations"])
app.include_router(research.router, prefix="/api/v1", tags=["research"])

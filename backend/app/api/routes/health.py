"""Health check. Must trigger zero provider/NSE calls and zero expensive
initialization — it does not touch any dependency."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.schemas.common import HealthResponse

router = APIRouter()

_SERVICE_NAME = "TradeLens API"
_SERVICE_VERSION = "0.1.0"


@router.get("/health", response_model=HealthResponse, summary="Service health check")
def health() -> HealthResponse:
    return HealthResponse(status="ok", service=_SERVICE_NAME, version=_SERVICE_VERSION)

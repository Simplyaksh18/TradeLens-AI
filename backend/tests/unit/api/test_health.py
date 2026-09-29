"""Health endpoint must never touch any dependency: no NSE, no Yahoo, no
cache/instrument-master initialization."""

from fastapi.testclient import TestClient

from app.api.dependencies import get_instrument_master, get_market_data_service
from app.main import app


def _fail_if_called():
    raise AssertionError("health endpoint must not touch any dependency")


def test_health_returns_stable_payload():
    app.dependency_overrides[get_instrument_master] = _fail_if_called
    app.dependency_overrides[get_market_data_service] = _fail_if_called
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "TradeLens API", "version": "0.1.0"}

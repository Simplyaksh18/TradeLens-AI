"""Full domain-error -> HTTP mapping table (CLAUDE.md Phase 1E section 20)."""

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_instrument_master, get_market_data_service
from app.core.exceptions import (
    InstrumentCatalogUnavailableError,
    MalformedProviderResponseError,
    RateLimitedError,
    UnclassifiedProviderError,
)
from app.main import app
from tests.unit.api.conftest import FakeMarketDataService


@pytest.mark.parametrize(
    "exc, expected_status, expected_code",
    [
        (RateLimitedError("throttled"), 503, "PROVIDER_RATE_LIMITED"),
        (MalformedProviderResponseError("bad shape"), 502, "UPSTREAM_PROVIDER_ERROR"),
        (UnclassifiedProviderError("weird"), 502, "UPSTREAM_PROVIDER_ERROR"),
    ],
)
def test_domain_error_mapping(client, exc, expected_status, expected_code):
    failing_service = FakeMarketDataService(raise_exc=exc)
    app.dependency_overrides[get_market_data_service] = lambda: failing_service

    response = client.get(
        "/api/v1/market-data/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-01-05", "interval": "1d"},
    )

    assert response.status_code == expected_status
    assert response.json()["error"]["code"] == expected_code


def test_error_body_never_exposes_traceback_or_exception_class_name(client):
    failing_service = FakeMarketDataService(raise_exc=RateLimitedError("throttled"))
    app.dependency_overrides[get_market_data_service] = lambda: failing_service

    response = client.get(
        "/api/v1/market-data/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-01-05", "interval": "1d"},
    )

    text = response.text
    assert "Traceback" not in text
    assert "RateLimitedError" not in text
    assert set(response.json().keys()) == {"error"}
    assert set(response.json()["error"].keys()) == {"code", "message"}


def test_malformed_date_syntax_returns_request_validation_error(client):
    response = client.get(
        "/api/v1/market-data/RELIANCE",
        params={"start": "not-a-date", "end": "2024-01-05", "interval": "1d"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REQUEST_VALIDATION_ERROR"


class _FailingInstrumentMaster:
    """Minimal stand-in that always raises whatever exception the clean-
    deploy bootstrap would surface (see app.instruments.master), so the
    route/error-mapping layer can be tested without a real filesystem."""

    def __init__(self, exc: Exception):
        self._exc = exc

    def search(self, query: str, limit: int = 20):
        raise self._exc

    def resolve(self, symbol: str):
        raise self._exc


def test_instrument_catalog_unavailable_maps_to_503(client):
    app.dependency_overrides[get_instrument_master] = lambda: _FailingInstrumentMaster(InstrumentCatalogUnavailableError())

    response = client.get("/api/v1/instruments", params={"q": "RELIANCE"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "INSTRUMENT_CATALOG_UNAVAILABLE"
    assert "Traceback" not in response.text
    assert "FileNotFoundError" not in response.text


def test_unmapped_exception_returns_generic_500_never_a_raw_traceback():
    """A genuinely unexpected exception (nothing to do with this specific
    bug -- any future unhandled bug) must still produce a clean, mapped
    JSON response rather than propagating past CORSMiddleware. Uses a
    dedicated TestClient(raise_server_exceptions=False) so the real HTTP
    response is observed, matching how a browser would actually see it,
    instead of pytest re-raising the exception into the test process."""
    app.dependency_overrides[get_instrument_master] = lambda: _FailingInstrumentMaster(RuntimeError("boom"))
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            response = test_client.get("/api/v1/instruments", params={"q": "RELIANCE"})
    finally:
        app.dependency_overrides.pop(get_instrument_master, None)

    assert response.status_code == 500
    assert response.json() == {"error": {"code": "INTERNAL_SERVER_ERROR", "message": "An unexpected server error occurred."}}
    assert "Traceback" not in response.text
    assert "RuntimeError" not in response.text
    assert "boom" not in response.text


def test_unmapped_exception_response_still_carries_cors_headers_for_an_allowed_origin():
    """The specific, previously-misleading production symptom this
    catch-all handler fixes: without it, an unhandled exception's response
    has no Access-Control-Allow-Origin header, so the browser reports the
    request to the frontend as an opaque, indistinguishable-from-offline
    network failure instead of a real (if generic) 500. See CLAUDE.md
    deployment-compatibility notes."""
    app.dependency_overrides[get_instrument_master] = lambda: _FailingInstrumentMaster(RuntimeError("boom"))
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            response = test_client.get(
                "/api/v1/instruments",
                params={"q": "RELIANCE"},
                headers={"Origin": "http://localhost:5173"},
            )
    finally:
        app.dependency_overrides.pop(get_instrument_master, None)

    assert response.status_code == 500
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_data_that_fails_phase1b_validation_maps_indicator_error_to_500(client):
    # A realistic case: the provider itself returns data that structurally
    # passes Phase 1A normalization but fails Phase 1B validation (e.g. an
    # inverted OHLC bar) -- compute_indicators refuses to run on it.
    from datetime import date

    from app.market_data.models import OHLCVBar, OHLCVSeries

    bad_bar = OHLCVBar(date=date(2024, 1, 1), open=100, high=90, low=95, close=105, adj_close=100, volume=500)
    bad_series = OHLCVSeries(provider_symbol="RELIANCE.NS", interval="1d", bars=(bad_bar,))
    service_with_bad_data = FakeMarketDataService(series=bad_series)
    app.dependency_overrides[get_market_data_service] = lambda: service_with_bad_data

    response = client.get(
        "/api/v1/indicators/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-01-01", "interval": "1d"},
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_DATA_CONTRACT_ERROR"

"""Full domain-error -> HTTP mapping table (CLAUDE.md Phase 1E section 20)."""

import pytest

from app.api.dependencies import get_market_data_service
from app.core.exceptions import (
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

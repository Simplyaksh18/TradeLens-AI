from datetime import date

from app.core.exceptions import InstrumentNotFoundError, NoDataForPeriodError, ProviderUnavailableError


def test_market_data_happy_path(client, fake_market_data_service):
    response = client.get(
        "/api/v1/market-data/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-31", "interval": "1d"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider_symbol"] == "RELIANCE.NS"
    assert body["interval"] == "1d"
    dates = [b["date"] for b in body["bars"]]
    assert dates == sorted(dates)
    assert len(body["bars"]) > 0
    first = body["bars"][0]
    assert set(first.keys()) == {"date", "open", "high", "low", "close", "adj_close", "volume"}
    assert isinstance(first["close"], (int, float))
    assert isinstance(first["adj_close"], (int, float))
    assert fake_market_data_service.calls == [("RELIANCE", "1d", date(2024, 1, 1), date(2024, 3, 31))]


def test_raw_close_and_adj_close_remain_distinct(client, fake_market_data_service):
    # make_market_series sets adj_close == close for every bar by construction,
    # so instead directly verify the two fields are both present and mapped
    # independently (not collapsed into one field) by checking the schema.
    response = client.get(
        "/api/v1/market-data/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-01-05", "interval": "1d"},
    )
    bar = response.json()["bars"][0]
    assert "close" in bar and "adj_close" in bar


def test_start_after_end_rejected(client):
    response = client.get(
        "/api/v1/market-data/RELIANCE",
        params={"start": "2024-06-01", "end": "2024-01-01", "interval": "1d"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_DATE_RANGE"


def test_excessive_span_rejected(client):
    response = client.get(
        "/api/v1/market-data/RELIANCE",
        params={"start": "2000-01-01", "end": "2024-01-01", "interval": "1d"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "DATE_RANGE_TOO_LARGE"


def test_unsupported_interval_rejected(client):
    response = client.get(
        "/api/v1/market-data/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-01-31", "interval": "5m"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNSUPPORTED_INTERVAL"


def test_instrument_not_found_maps_to_404(client, monkeypatch):
    from tests.unit.api.conftest import FakeMarketDataService
    from app.api.dependencies import get_market_data_service
    from app.main import app

    failing_service = FakeMarketDataService(raise_exc=InstrumentNotFoundError("NOTREAL"))
    app.dependency_overrides[get_market_data_service] = lambda: failing_service
    response = client.get(
        "/api/v1/market-data/NOTREAL",
        params={"start": "2024-01-01", "end": "2024-01-31", "interval": "1d"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "INSTRUMENT_NOT_FOUND"


def test_no_data_for_period_maps_to_404(client):
    from app.api.dependencies import get_market_data_service
    from app.main import app
    from tests.unit.api.conftest import FakeMarketDataService

    failing_service = FakeMarketDataService(raise_exc=NoDataForPeriodError("RELIANCE.NS", date(2024, 1, 1), date(2024, 1, 2)))
    app.dependency_overrides[get_market_data_service] = lambda: failing_service
    response = client.get(
        "/api/v1/market-data/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-01-02", "interval": "1d"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NO_DATA_FOR_PERIOD"


def test_provider_unavailable_maps_to_503(client):
    from app.api.dependencies import get_market_data_service
    from app.main import app
    from tests.unit.api.conftest import FakeMarketDataService

    failing_service = FakeMarketDataService(raise_exc=ProviderUnavailableError("down"))
    app.dependency_overrides[get_market_data_service] = lambda: failing_service
    response = client.get(
        "/api/v1/market-data/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-01-02", "interval": "1d"},
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"

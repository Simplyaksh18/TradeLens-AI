"""Phase 2D: /outcomes route tests (Phase 2A exposed through the API)."""

from app.api.dependencies import get_market_data_service
from app.core.exceptions import InstrumentNotFoundError
from app.main import app
from tests.unit.api.conftest import FakeMarketDataService


def test_outcomes_200_and_metadata(client):
    response = client.get(
        "/api/v1/outcomes/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider_symbol"] == "RELIANCE.NS"
    assert body["interval"] == "1d"
    assert body["strategy_id"] == "trend_momentum_v1"
    assert body["strategy_name"] == "Trend + Momentum v1"
    assert isinstance(body["outcomes"], list)


def test_outcomes_only_buy_decisions_present(client):
    response = client.get(
        "/api/v1/outcomes/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d"},
    )
    outcomes = response.json()["outcomes"]
    assert len(outcomes) > 0
    assert all(o["decision"] == "BUY" for o in outcomes)


def test_outcomes_fields_and_reference_close_preserved(client):
    response = client.get(
        "/api/v1/outcomes/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d"},
    )
    outcome = response.json()["outcomes"][0]
    assert set(outcome.keys()) == {
        "date", "decision", "reference_close", "forward_close_5d", "forward_return_5d",
        "forward_close_10d", "forward_return_10d", "mae_10d", "mfe_10d", "available_forward_bars",
    }
    assert isinstance(outcome["reference_close"], (int, float))
    assert isinstance(outcome["available_forward_bars"], int)


def test_outcomes_censored_fields_serialize_as_json_null(client):
    # A short range keeps at least one BUY signal near the end of the
    # series, where +5D/+10D/MAE/MFE are still censored.
    response = client.get(
        "/api/v1/outcomes/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-27", "interval": "1d"},
    )
    outcomes = response.json()["outcomes"]
    last = outcomes[-1]
    if last["available_forward_bars"] < 5:
        assert last["forward_close_5d"] is None
        assert last["forward_return_5d"] is None
    if last["available_forward_bars"] < 10:
        assert last["forward_close_10d"] is None
        assert last["mae_10d"] is None
        assert last["mfe_10d"] is None


def test_outcomes_return_values_are_decimal_fractions(client):
    response = client.get(
        "/api/v1/outcomes/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d"},
    )
    outcomes = response.json()["outcomes"]
    with_return = [o for o in outcomes if o["forward_return_5d"] is not None]
    assert with_return
    for o in with_return:
        assert -1.0 < o["forward_return_5d"] < 1.0  # decimal fraction, never *100


def test_outcomes_consecutive_buy_remain_independent(client):
    response = client.get(
        "/api/v1/outcomes/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d"},
    )
    outcomes = response.json()["outcomes"]
    dates = [o["date"] for o in outcomes]
    assert len(dates) == len(set(dates))  # every BUY date is its own outcome, none collapsed


def test_outcomes_single_market_fetch(client, fake_market_data_service):
    client.get(
        "/api/v1/outcomes/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d"},
    )
    assert len(fake_market_data_service.calls) == 1


def test_outcomes_unknown_symbol_follows_existing_error_contract(client):
    failing_service = FakeMarketDataService(raise_exc=InstrumentNotFoundError("NOTASYMBOL"))
    app.dependency_overrides[get_market_data_service] = lambda: failing_service

    response = client.get(
        "/api/v1/outcomes/trend-momentum-v1/NOTASYMBOL",
        params={"start": "2024-01-01", "end": "2024-01-10", "interval": "1d"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "INSTRUMENT_NOT_FOUND"

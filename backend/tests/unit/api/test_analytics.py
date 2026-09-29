"""Phase 2D: /analytics route tests (Phase 2C exposed through the API).

Also serves as the required end-to-end integration fixture: mocked
normalized OHLCV -> real indicator engine -> real strategy engine -> real
Phase 2B backtester -> real Phase 2C analytics -> FastAPI serialization.
The only mocked boundary is FakeMarketDataService (external market-data
retrieval); everything else is the real deterministic pipeline.
"""

from app.api.dependencies import get_market_data_service
from app.core.exceptions import InstrumentNotFoundError
from app.main import app
from tests.unit.api.conftest import FakeMarketDataService

EXPECTED_FIELDS = {
    "provider_symbol", "interval", "strategy_id", "strategy_name",
    "initial_equity", "ending_equity", "total_return",
    "realized_pnl", "unrealized_pnl", "total_pnl",
    "closed_trade_count", "winner_count", "loser_count", "breakeven_count", "win_rate",
    "average_trade_return", "median_trade_return", "best_trade_return", "worst_trade_return",
    "peak_equity",
    "maximum_drawdown", "max_drawdown_peak_date", "max_drawdown_trough_date",
    "exposed_bar_count", "total_bar_count", "exposure",
    "drawdown_series",
}


def test_analytics_200(client):
    response = client.get(
        "/api/v1/analytics/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d"},
    )
    assert response.status_code == 200


def test_analytics_full_pipeline_integration_and_accepted_fields(client):
    """The end-to-end fixture: real indicators/strategy/backtest/analytics,
    only market-data fetch mocked."""
    response = client.get(
        "/api/v1/analytics/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d"},
    )
    body = response.json()
    assert set(body.keys()) == EXPECTED_FIELDS
    assert body["provider_symbol"] == "RELIANCE.NS"
    assert body["strategy_id"] == "trend_momentum_v1"
    assert isinstance(body["total_bar_count"], int) and body["total_bar_count"] > 0
    assert len(body["drawdown_series"]) == body["total_bar_count"]


def test_analytics_total_return_is_decimal(client):
    response = client.get(
        "/api/v1/analytics/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d"},
    )
    total_return = response.json()["total_return"]
    assert isinstance(total_return, (int, float))
    assert -1.0 < total_return < 1.0  # decimal fraction, never *100


def test_analytics_maximum_drawdown_is_negative_or_zero(client):
    response = client.get(
        "/api/v1/analytics/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d"},
    )
    assert response.json()["maximum_drawdown"] <= 0


def test_analytics_max_dd_dates_serialized(client):
    response = client.get(
        "/api/v1/analytics/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d"},
    )
    body = response.json()
    assert body["max_drawdown_peak_date"] is not None
    assert body["max_drawdown_trough_date"] is not None


def test_analytics_open_position_not_counted_as_closed_trade(client):
    # Short window likely to end with an open position.
    response = client.get(
        "/api/v1/analytics/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-15", "interval": "1d"},
    )
    backtest_response = client.get(
        "/api/v1/backtests/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-15", "interval": "1d"},
    )
    analytics_body = response.json()
    backtest_body = backtest_response.json()
    if backtest_body["open_position"] is not None:
        assert analytics_body["closed_trade_count"] == len(backtest_body["trades"])


def test_analytics_exposure_serialized(client):
    response = client.get(
        "/api/v1/analytics/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d"},
    )
    body = response.json()
    assert 0.0 <= body["exposure"] <= 1.0
    assert body["exposed_bar_count"] <= body["total_bar_count"]


def test_analytics_none_metrics_serialize_as_json_null(client):
    # A window with no closed trades yet -> distribution/win_rate fields None.
    response = client.get(
        "/api/v1/analytics/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-02-01", "interval": "1d"},
    )
    body = response.json()
    if body["closed_trade_count"] == 0:
        assert body["win_rate"] is None
        assert body["average_trade_return"] is None
        assert body["median_trade_return"] is None
        assert body["best_trade_return"] is None
        assert body["worst_trade_return"] is None


def test_analytics_annualized_volatility_absent(client):
    response = client.get(
        "/api/v1/analytics/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d"},
    )
    assert "annualized_volatility" not in response.json()


def test_analytics_deferred_metrics_absent(client):
    response = client.get(
        "/api/v1/analytics/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d"},
    )
    body = response.json()
    for forbidden in ("cagr", "sharpe", "sharpe_ratio", "sortino", "sortino_ratio", "calmar", "alpha", "beta", "var", "cvar"):
        assert forbidden not in body


def test_analytics_custom_initial_capital(client):
    response = client.get(
        "/api/v1/analytics/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d", "initial_capital": 5000},
    )
    assert response.json()["initial_equity"] == 5000.0


def test_analytics_zero_initial_capital_rejected(client):
    response = client.get(
        "/api/v1/analytics/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d", "initial_capital": 0},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_INITIAL_CAPITAL"


def test_analytics_unknown_symbol_follows_existing_error_contract(client):
    failing_service = FakeMarketDataService(raise_exc=InstrumentNotFoundError("NOTASYMBOL"))
    app.dependency_overrides[get_market_data_service] = lambda: failing_service

    response = client.get(
        "/api/v1/analytics/trend-momentum-v1/NOTASYMBOL",
        params={"start": "2024-01-01", "end": "2024-01-10", "interval": "1d"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "INSTRUMENT_NOT_FOUND"


def test_analytics_single_market_fetch(client, fake_market_data_service):
    client.get(
        "/api/v1/analytics/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d"},
    )
    assert len(fake_market_data_service.calls) == 1

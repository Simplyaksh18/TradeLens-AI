"""Phase 2D: /backtests route tests (Phase 2B exposed through the API)."""

from app.api.dependencies import get_market_data_service
from app.core.exceptions import InstrumentNotFoundError
from app.main import app
from tests.unit.api.conftest import FakeMarketDataService


def test_backtest_200(client):
    response = client.get(
        "/api/v1/backtests/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d"},
    )
    assert response.status_code == 200


def test_backtest_default_initial_capital(client):
    response = client.get(
        "/api/v1/backtests/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d"},
    )
    assert response.json()["config"]["initial_capital"] == 100_000.0
    assert response.json()["config"]["transaction_cost"] == 0.0
    assert response.json()["config"]["slippage"] == 0.0


def test_backtest_custom_initial_capital(client):
    response = client.get(
        "/api/v1/backtests/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d", "initial_capital": 5000},
    )
    assert response.json()["config"]["initial_capital"] == 5000.0


def test_backtest_next_bar_execution_and_signal_vs_execution_dates(client):
    response = client.get(
        "/api/v1/backtests/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d"},
    )
    body = response.json()
    trade_or_open = (body["trades"][0] if body["trades"] else body["open_position"])
    assert trade_or_open is not None
    assert trade_or_open["entry_signal_date"] != trade_or_open["entry_date"]  # T vs T+1


def test_backtest_closed_trades_serialize_all_fields(client):
    response = client.get(
        "/api/v1/backtests/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d"},
    )
    trades = response.json()["trades"]
    if trades:
        trade = trades[0]
        assert set(trade.keys()) == {
            "entry_signal_date", "entry_date", "entry_price", "exit_signal_date", "exit_date",
            "exit_price", "quantity", "gross_pnl", "gross_return", "net_pnl",
        }
        assert trade["net_pnl"] == trade["gross_pnl"]  # V1 zero-cost baseline


def test_backtest_open_position_distinct_from_closed_trade(client):
    # A short window ending mid-BUY-run leaves a position open, not closed.
    response = client.get(
        "/api/v1/backtests/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-15", "interval": "1d"},
    )
    body = response.json()
    if body["open_position"] is not None:
        assert "pending_exit_signal_date" in body["open_position"]
        assert body["open_position"] not in body["trades"]


def test_backtest_pending_entry_state_serialized_field_present(client):
    response = client.get(
        "/api/v1/backtests/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d"},
    )
    assert "pending_entry_signal_date" in response.json()


def test_backtest_equity_curve_serialized(client):
    response = client.get(
        "/api/v1/backtests/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-01-10", "interval": "1d"},
    )
    equity_curve = response.json()["equity_curve"]
    assert len(equity_curve) > 0
    point = equity_curve[0]
    assert set(point.keys()) == {"date", "cash", "position_quantity", "position_market_value", "equity"}


def test_backtest_route_does_not_calculate_analytics(client):
    response = client.get(
        "/api/v1/backtests/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d"},
    )
    body = response.json()
    for forbidden in ("total_return", "maximum_drawdown", "win_rate", "drawdown_series", "annualized_volatility"):
        assert forbidden not in body


def test_backtest_zero_initial_capital_rejected(client):
    response = client.get(
        "/api/v1/backtests/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d", "initial_capital": 0},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_INITIAL_CAPITAL"


def test_backtest_negative_initial_capital_rejected(client):
    response = client.get(
        "/api/v1/backtests/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d", "initial_capital": -100},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_INITIAL_CAPITAL"


def test_backtest_unknown_symbol_follows_existing_error_contract(client):
    failing_service = FakeMarketDataService(raise_exc=InstrumentNotFoundError("NOTASYMBOL"))
    app.dependency_overrides[get_market_data_service] = lambda: failing_service

    response = client.get(
        "/api/v1/backtests/trend-momentum-v1/NOTASYMBOL",
        params={"start": "2024-01-01", "end": "2024-01-10", "interval": "1d"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "INSTRUMENT_NOT_FOUND"


def test_backtest_single_market_fetch(client, fake_market_data_service):
    client.get(
        "/api/v1/backtests/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d"},
    )
    assert len(fake_market_data_service.calls) == 1

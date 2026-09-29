"""Phase 2C: performance & risk analytics engine tests.

Builds `BacktestResult` objects directly (rather than running Phase 2B)
for full control over the exact equity/trade fixtures needed to hand-verify
each metric.
"""

import copy
from datetime import date, timedelta

import pytest

from app.analytics.engine import compute_performance_analytics
from app.analytics.models import PerformanceAnalytics
from app.backtesting.models import BacktestConfig, BacktestResult, EquityPoint, ExecutedTrade, OpenPosition
from app.core.exceptions import AnalyticsInputInvalidError

SYMBOL = "X.NS"
INTERVAL = "1d"
STRATEGY_ID = "trend_momentum_v1"
STRATEGY_NAME = "Trend + Momentum v1"


def _dates(n: int, start: date = date(2024, 1, 1)) -> list[date]:
    return [start + timedelta(days=i) for i in range(n)]


def _point(d: date, cash: float, quantity: int = 0, market_value: float = 0.0) -> EquityPoint:
    return EquityPoint(date=d, cash=cash, position_quantity=quantity, position_market_value=market_value, equity=cash + market_value)


def _trade(entry_date, exit_date, entry_price, exit_price, quantity=1, entry_signal_date=None, exit_signal_date=None):
    gross_pnl = (exit_price - entry_price) * quantity
    gross_return = exit_price / entry_price - 1
    return ExecutedTrade(
        entry_signal_date=entry_signal_date or entry_date,
        entry_date=entry_date,
        entry_price=entry_price,
        exit_signal_date=exit_signal_date or exit_date,
        exit_date=exit_date,
        exit_price=exit_price,
        quantity=quantity,
        gross_pnl=gross_pnl,
        gross_return=gross_return,
        net_pnl=gross_pnl,
    )


def _result(equity_curve, trades=(), open_position=None, config=None, symbol=SYMBOL, interval=INTERVAL):
    return BacktestResult(
        provider_symbol=symbol,
        interval=interval,
        strategy_id=STRATEGY_ID,
        strategy_name=STRATEGY_NAME,
        config=config or BacktestConfig(),
        trades=tuple(trades),
        open_position=open_position,
        pending_entry_signal_date=None,
        equity_curve=tuple(equity_curve),
    )


# ---------------------------------------------------------------------------
# 17/18/19/20/21/22/23: drawdown hand fixture + tie policy
# ---------------------------------------------------------------------------


def test_drawdown_series_and_max_drawdown_hand_derived():
    dates = _dates(6)
    values = [1000.0, 1200.0, 1080.0, 900.0, 1100.0, 1300.0]
    equity_curve = [_point(d, v) for d, v in zip(dates, values)]
    result = _result(equity_curve)

    analytics = compute_performance_analytics(result)

    expected_peaks = [1000.0, 1200.0, 1200.0, 1200.0, 1200.0, 1300.0]
    expected_drawdowns = [0.0, 0.0, -0.10, -0.25, 1100.0 / 1200.0 - 1, 0.0]

    assert [dp.running_peak for dp in analytics.drawdown_series] == pytest.approx(expected_peaks)
    assert [dp.drawdown for dp in analytics.drawdown_series] == pytest.approx(expected_drawdowns)
    assert all(dp.drawdown <= 0 for dp in analytics.drawdown_series)

    assert analytics.maximum_drawdown == pytest.approx(-0.25)
    assert analytics.max_drawdown_peak_date == dates[1]  # date of 1200
    assert analytics.max_drawdown_trough_date == dates[3]  # date of 900
    assert analytics.peak_equity == pytest.approx(1300.0)


def test_repeated_equal_peak_preserves_earlier_peak_date():
    dates = _dates(4)
    values = [1000.0, 1200.0, 1200.0, 900.0]  # peak repeats at index 1 and 2
    equity_curve = [_point(d, v) for d, v in zip(dates, values)]
    result = _result(equity_curve)

    analytics = compute_performance_analytics(result)

    assert analytics.max_drawdown_peak_date == dates[1]  # first occurrence, not index 2


def test_repeated_equal_maximum_drawdown_preserves_first_trough():
    dates = _dates(5)
    values = [1000.0, 900.0, 1000.0, 900.0, 1000.0]  # -0.10 drawdown at index 1 and 3
    equity_curve = [_point(d, v) for d, v in zip(dates, values)]
    result = _result(equity_curve)

    analytics = compute_performance_analytics(result)

    assert analytics.maximum_drawdown == pytest.approx(-0.10)
    assert analytics.max_drawdown_trough_date == dates[1]  # first occurrence


def test_new_high_has_zero_drawdown():
    dates = _dates(3)
    values = [1000.0, 1100.0, 1200.0]
    equity_curve = [_point(d, v) for d, v in zip(dates, values)]
    result = _result(equity_curve)

    analytics = compute_performance_analytics(result)

    assert all(dp.drawdown == 0.0 for dp in analytics.drawdown_series)
    assert analytics.maximum_drawdown == 0.0


def test_monotonic_rising_equity_max_drawdown_zero():
    dates = _dates(4)
    values = [1000.0, 1050.0, 1100.0, 1150.0]
    equity_curve = [_point(d, v) for d, v in zip(dates, values)]
    result = _result(equity_curve)

    analytics = compute_performance_analytics(result)

    assert analytics.maximum_drawdown == 0.0
    # Every point has drawdown 0.0 on a monotonic rise; first-occurrence tie
    # policy picks the FIRST such point, not the last.
    assert analytics.max_drawdown_peak_date == dates[0]
    assert analytics.max_drawdown_trough_date == dates[0]


# ---------------------------------------------------------------------------
# 1/2/3/4/5/6: total return, P&L invariant, closed vs open population
# ---------------------------------------------------------------------------


def test_total_return_and_total_pnl_hand_derived():
    dates = _dates(2)
    equity_curve = [_point(dates[0], 1000.0), _point(dates[1], 1180.0)]
    trade = _trade(dates[0], dates[1], entry_price=110.0, exit_price=130.0, quantity=9)  # net_pnl = 180
    result = _result(equity_curve, trades=[trade])

    analytics = compute_performance_analytics(result)

    assert analytics.initial_equity == pytest.approx(1000.0)
    assert analytics.ending_equity == pytest.approx(1180.0)
    assert analytics.total_pnl == pytest.approx(180.0)
    assert analytics.total_return == pytest.approx(0.18)
    assert analytics.realized_pnl == pytest.approx(180.0)
    assert analytics.unrealized_pnl == pytest.approx(0.0)
    assert analytics.realized_pnl + analytics.unrealized_pnl == pytest.approx(analytics.total_pnl)


def test_no_open_position_unrealized_pnl_is_zero():
    dates = _dates(2)
    equity_curve = [_point(dates[0], 500.0), _point(dates[1], 500.0)]
    result = _result(equity_curve, trades=(), open_position=None)

    analytics = compute_performance_analytics(result)

    assert analytics.unrealized_pnl == 0.0


def test_open_position_unrealized_pnl_and_exclusion_from_closed_stats():
    dates = _dates(2)
    # Open position: entry_price=100, quantity=10 -> cost basis 1000.
    # Final mark-to-market position_market_value = 1150 (close moved to 115).
    equity_curve = [_point(dates[0], 0.0, quantity=10, market_value=1000.0), _point(dates[1], 0.0, quantity=10, market_value=1150.0)]
    open_position = OpenPosition(
        entry_signal_date=dates[0], entry_date=dates[0], entry_price=100.0, quantity=10, pending_exit_signal_date=None
    )
    result = _result(equity_curve, trades=(), open_position=open_position)

    analytics = compute_performance_analytics(result)

    # 5/6: open position contributes to equity/unrealized P&L...
    assert analytics.unrealized_pnl == pytest.approx(1150.0 - 100.0 * 10)
    assert analytics.unrealized_pnl == pytest.approx(150.0)
    assert analytics.ending_equity == pytest.approx(1150.0)
    assert analytics.total_return == pytest.approx(1150.0 / 1000.0 - 1)
    # ...but is NOT counted as a closed trade.
    assert analytics.closed_trade_count == 0
    assert analytics.winner_count == 0
    assert analytics.loser_count == 0
    assert analytics.breakeven_count == 0
    assert analytics.win_rate is None


# ---------------------------------------------------------------------------
# 7/8/9/10/11: closed-trade counts, win rate
# ---------------------------------------------------------------------------


def test_winner_loser_breakeven_counts_and_invariant():
    dates = _dates(2)
    equity_curve = [_point(dates[0], 1000.0), _point(dates[1], 1000.0)]
    trades = [
        _trade(dates[0], dates[1], 100.0, 110.0),  # winner
        _trade(dates[0], dates[1], 100.0, 95.0),  # loser
        _trade(dates[0], dates[1], 100.0, 100.0),  # breakeven
    ]
    result = _result(equity_curve, trades=trades)

    analytics = compute_performance_analytics(result)

    assert analytics.closed_trade_count == 3
    assert analytics.winner_count == 1
    assert analytics.loser_count == 1
    assert analytics.breakeven_count == 1
    assert analytics.winner_count + analytics.loser_count + analytics.breakeven_count == analytics.closed_trade_count


def test_no_closed_trades_win_rate_is_none_not_zero():
    dates = _dates(2)
    equity_curve = [_point(dates[0], 1000.0), _point(dates[1], 1000.0)]
    result = _result(equity_curve, trades=())

    analytics = compute_performance_analytics(result)

    assert analytics.closed_trade_count == 0
    assert analytics.win_rate is None  # "no observations" != "0% winners"


# ---------------------------------------------------------------------------
# 12/13/14/15/16: trade return distribution hand fixture
# ---------------------------------------------------------------------------


def test_trade_return_distribution_hand_derived():
    dates = _dates(2)
    equity_curve = [_point(dates[0], 1000.0), _point(dates[1], 1000.0)]
    trades = [
        _trade(dates[0], dates[1], 100.0, 110.0),  # +0.10
        _trade(dates[0], dates[1], 100.0, 95.0),  # -0.05
        _trade(dates[0], dates[1], 100.0, 100.0),  # 0.00
        _trade(dates[0], dates[1], 100.0, 120.0),  # +0.20
    ]
    result = _result(equity_curve, trades=trades)

    analytics = compute_performance_analytics(result)

    assert analytics.win_rate == pytest.approx(0.5)
    assert analytics.average_trade_return == pytest.approx(0.0625)
    assert analytics.median_trade_return == pytest.approx(0.05)
    assert analytics.best_trade_return == pytest.approx(0.20)
    assert analytics.worst_trade_return == pytest.approx(-0.05)


def test_zero_trades_distribution_metrics_are_none():
    dates = _dates(2)
    equity_curve = [_point(dates[0], 1000.0), _point(dates[1], 1000.0)]
    result = _result(equity_curve, trades=())

    analytics = compute_performance_analytics(result)

    assert analytics.average_trade_return is None
    assert analytics.median_trade_return is None
    assert analytics.best_trade_return is None
    assert analytics.worst_trade_return is None


# ---------------------------------------------------------------------------
# 24/25/26: exposure
# ---------------------------------------------------------------------------


def test_exposure_zero_when_always_flat():
    dates = _dates(4)
    equity_curve = [_point(d, 1000.0) for d in dates]
    result = _result(equity_curve)

    analytics = compute_performance_analytics(result)

    assert analytics.exposed_bar_count == 0
    assert analytics.total_bar_count == 4
    assert analytics.exposure == pytest.approx(0.0)


def test_exposure_one_when_always_invested():
    dates = _dates(4)
    equity_curve = [_point(d, 0.0, quantity=5, market_value=500.0) for d in dates]
    result = _result(equity_curve)

    analytics = compute_performance_analytics(result)

    assert analytics.exposed_bar_count == 4
    assert analytics.exposure == pytest.approx(1.0)


def test_exposure_partial_hand_derived():
    dates = _dates(5)
    equity_curve = [
        _point(dates[0], 1000.0),
        _point(dates[1], 0.0, quantity=5, market_value=500.0),
        _point(dates[2], 0.0, quantity=5, market_value=520.0),
        _point(dates[3], 1000.0),
        _point(dates[4], 1000.0),
    ]
    result = _result(equity_curve)

    analytics = compute_performance_analytics(result)

    assert analytics.exposed_bar_count == 2
    assert analytics.total_bar_count == 5
    assert analytics.exposure == pytest.approx(2 / 5)


# ---------------------------------------------------------------------------
# 32/33/34/35/36: rejection of malformed/structurally invalid input
# ---------------------------------------------------------------------------


def test_empty_equity_curve_rejected():
    result = _result(equity_curve=())
    with pytest.raises(AnalyticsInputInvalidError):
        compute_performance_analytics(result)


def test_nan_equity_rejected():
    dates = _dates(2)
    equity_curve = [_point(dates[0], 1000.0), EquityPoint(date=dates[1], cash=float("nan"), position_quantity=0, position_market_value=0.0, equity=float("nan"))]
    result = _result(equity_curve)
    with pytest.raises(AnalyticsInputInvalidError):
        compute_performance_analytics(result)


def test_infinite_equity_rejected():
    dates = _dates(2)
    equity_curve = [_point(dates[0], 1000.0), EquityPoint(date=dates[1], cash=float("inf"), position_quantity=0, position_market_value=0.0, equity=float("inf"))]
    result = _result(equity_curve)
    with pytest.raises(AnalyticsInputInvalidError):
        compute_performance_analytics(result)


def test_negative_position_market_value_rejected():
    dates = _dates(2)
    equity_curve = [_point(dates[0], 1000.0), EquityPoint(date=dates[1], cash=1000.0, position_quantity=1, position_market_value=-5.0, equity=995.0)]
    result = _result(equity_curve)
    with pytest.raises(AnalyticsInputInvalidError):
        compute_performance_analytics(result)


def test_non_chronological_equity_dates_rejected():
    dates = _dates(3)
    equity_curve = [_point(dates[0], 1000.0), _point(dates[2], 1010.0), _point(dates[1], 1020.0)]
    result = _result(equity_curve)
    with pytest.raises(AnalyticsInputInvalidError):
        compute_performance_analytics(result)


def test_duplicate_equity_dates_rejected():
    d0 = date(2024, 1, 1)
    equity_curve = [_point(d0, 1000.0), _point(d0, 1010.0)]
    result = _result(equity_curve)
    with pytest.raises(AnalyticsInputInvalidError):
        compute_performance_analytics(result)


def test_zero_initial_capital_config_rejected():
    dates = _dates(2)
    equity_curve = [_point(dates[0], 1000.0), _point(dates[1], 1010.0)]
    result = _result(equity_curve, config=BacktestConfig(initial_capital=0.0))
    with pytest.raises(AnalyticsInputInvalidError):
        compute_performance_analytics(result)


def test_nonfinite_trade_return_rejected():
    dates = _dates(2)
    equity_curve = [_point(dates[0], 1000.0), _point(dates[1], 1000.0)]
    bad_trade = ExecutedTrade(
        entry_signal_date=dates[0], entry_date=dates[0], entry_price=100.0,
        exit_signal_date=dates[1], exit_date=dates[1], exit_price=110.0,
        quantity=1, gross_pnl=10.0, gross_return=float("nan"), net_pnl=10.0,
    )
    result = _result(equity_curve, trades=[bad_trade])
    with pytest.raises(AnalyticsInputInvalidError):
        compute_performance_analytics(result)


def test_open_position_invalid_entry_price_rejected():
    dates = _dates(2)
    equity_curve = [_point(dates[0], 0.0, quantity=1, market_value=100.0), _point(dates[1], 0.0, quantity=1, market_value=100.0)]
    open_position = OpenPosition(entry_signal_date=dates[0], entry_date=dates[0], entry_price=-1.0, quantity=1, pending_exit_signal_date=None)
    result = _result(equity_curve, open_position=open_position)
    with pytest.raises(AnalyticsInputInvalidError):
        compute_performance_analytics(result)


# ---------------------------------------------------------------------------
# 37/38: determinism, non-mutation
# ---------------------------------------------------------------------------


def test_deterministic_repeated_calculation():
    dates = _dates(3)
    equity_curve = [_point(dates[0], 1000.0), _point(dates[1], 1100.0), _point(dates[2], 1050.0)]
    trades = [_trade(dates[0], dates[1], 100.0, 110.0)]
    result = _result(equity_curve, trades=trades)

    a = compute_performance_analytics(result)
    b = compute_performance_analytics(result)

    assert a == b


def test_no_input_mutation():
    dates = _dates(3)
    equity_curve = [_point(dates[0], 1000.0), _point(dates[1], 1100.0), _point(dates[2], 1050.0)]
    trades = [_trade(dates[0], dates[1], 100.0, 110.0)]
    result = _result(equity_curve, trades=trades)
    result_before = copy.deepcopy(result)

    compute_performance_analytics(result)

    assert result == result_before


def test_analytics_result_type():
    dates = _dates(2)
    equity_curve = [_point(dates[0], 1000.0), _point(dates[1], 1000.0)]
    result = _result(equity_curve)
    analytics = compute_performance_analytics(result)
    assert isinstance(analytics, PerformanceAnalytics)

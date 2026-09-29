"""Phase 2B: deterministic backtesting engine tests.

Frozen V1 execution model under test (see CLAUDE.md Phase 2B): a BUY/
NO_SIGNAL evaluation observed at bar T's Close can only affect execution
starting at bar T+1's OPEN; consecutive BUY while LONG creates no new
entry; the first NO_SIGNAL while LONG schedules the exit; INSUFFICIENT_DATA
never triggers any action; end-of-data never fabricates a fill.
"""

import copy
from datetime import date, timedelta

import pytest

from app.backtesting.engine import run_backtest
from app.backtesting.models import BacktestConfig, BacktestResult
from app.core.exceptions import BacktestInputInvalidError
from app.market_data.models import OHLCVBar, OHLCVSeries
from app.strategies.models import StrategyDecision, StrategyEvaluation, StrategyEvaluationSeries

SYMBOL = "X.NS"
INTERVAL = "1d"
STRATEGY_ID = "trend_momentum_v1"
STRATEGY_NAME = "Trend + Momentum v1"


def _dates(n: int, start: date = date(2024, 1, 1)) -> list[date]:
    # Irregular gaps (weekend/holiday-like) -- chronology, not calendar
    # spacing, is what the engine must respect.
    gaps = [1, 1, 3, 1, 3, 1, 1, 3]
    dates = [start]
    for i in range(n - 1):
        dates.append(dates[-1] + timedelta(days=gaps[i % len(gaps)]))
    return dates


def _bar(d: date, open_: float, close: float) -> OHLCVBar:
    high = max(open_, close) + 1
    low = min(open_, close) - 1
    # adj_close deliberately different from close to prove it's never used.
    return OHLCVBar(date=d, open=open_, high=high, low=low, close=close, adj_close=close * 0.5, volume=1000)


def _eval(d: date, decision: StrategyDecision) -> StrategyEvaluation:
    return StrategyEvaluation(
        date=d, strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME, decision=decision, conditions=(), missing_inputs=()
    )


def _build(ohlc, decisions, dates=None, symbol=SYMBOL, interval=INTERVAL):
    """ohlc: list of (open, close). decisions: list of StrategyDecision, same length."""
    assert len(ohlc) == len(decisions)
    if dates is None:
        dates = _dates(len(ohlc))
    bars = tuple(_bar(d, o, c) for d, (o, c) in zip(dates, ohlc))
    market = OHLCVSeries(provider_symbol=symbol, interval=interval, bars=bars)
    evals = tuple(_eval(d, dec) for d, dec in zip(dates, decisions))
    evaluations = StrategyEvaluationSeries(
        provider_symbol=symbol, interval=interval, strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME, evaluations=evals
    )
    return market, evaluations, dates


D = StrategyDecision


# ---------------------------------------------------------------------------
# Manual reference example (from the task spec) -- hand-derived fixture
# ---------------------------------------------------------------------------


def _manual_reference_fixture():
    """Day1 BUY, Day2 BUY, Day3 NO_SIGNAL, Day4 (exit bar)."""
    ohlc = [
        (100.0, 105.0),  # Day1: BUY
        (110.0, 120.0),  # Day2: BUY -- entry executes here at OPEN=110
        (115.0, 108.0),  # Day3: NO_SIGNAL -- schedules exit
        (130.0, 128.0),  # Day4: exit executes here at OPEN=130
    ]
    decisions = [D.BUY, D.BUY, D.NO_SIGNAL, D.NO_SIGNAL]
    return _build(ohlc, decisions)


def test_manual_reference_example_hand_derived():
    market, evaluations, dates = _manual_reference_fixture()
    result = run_backtest(market, evaluations, BacktestConfig(initial_capital=1000.0))

    assert len(result.trades) == 1
    trade = result.trades[0]

    # 1/2: entry at T+1 OPEN, never T's own OPEN.
    assert trade.entry_signal_date == dates[0]
    assert trade.entry_date == dates[1]
    assert trade.entry_price == pytest.approx(110.0)
    assert trade.entry_price != market.bars[0].open

    assert trade.quantity == 9  # floor(1000 / 110)
    assert trade.exit_signal_date == dates[2]
    assert trade.exit_date == dates[3]
    assert trade.exit_price == pytest.approx(130.0)

    assert trade.gross_pnl == pytest.approx((130.0 - 110.0) * 9)
    assert trade.gross_pnl == pytest.approx(180.0)
    assert trade.gross_return == pytest.approx(130.0 / 110.0 - 1)
    assert trade.gross_return == pytest.approx(0.18181818, rel=1e-6)
    assert trade.net_pnl == pytest.approx(trade.gross_pnl)  # V1 zero-cost baseline

    # Day2 end equity == 1090 (cash=10 after entry, + 9*close(120)).
    day2_equity = result.equity_curve[1]
    assert day2_equity.cash == pytest.approx(10.0)
    assert day2_equity.equity == pytest.approx(1090.0)

    # Final cash after exit == 1180.
    assert result.equity_curve[-1].cash == pytest.approx(1180.0)
    assert result.equity_curve[-1].equity == pytest.approx(1180.0)
    assert result.open_position is None
    assert result.pending_entry_signal_date is None


# ---------------------------------------------------------------------------
# 1/2/29c: next-bar entry, never same-bar OPEN
# ---------------------------------------------------------------------------


def test_buy_on_t_entry_at_t_plus_1_open():
    ohlc = [(100.0, 105.0), (200.0, 210.0)]
    decisions = [D.BUY, D.BUY]  # stays long, no exit yet -> open position
    market, evaluations, dates = _build(ohlc, decisions)

    result = run_backtest(market, evaluations, BacktestConfig(initial_capital=10_000.0))

    assert result.trades == ()
    assert result.open_position is not None
    assert result.open_position.entry_signal_date == dates[0]
    assert result.open_position.entry_date == dates[1]
    assert result.open_position.entry_price == pytest.approx(200.0)  # T+1 OPEN
    assert result.open_position.entry_price != market.bars[0].open  # never T's own OPEN


# ---------------------------------------------------------------------------
# 3: consecutive BUY while LONG creates exactly one entry
# ---------------------------------------------------------------------------


def test_consecutive_buy_while_long_creates_exactly_one_entry():
    ohlc = [(100.0, 101.0), (100.0, 101.0), (100.0, 101.0), (100.0, 101.0), (100.0, 101.0)]
    decisions = [D.BUY, D.BUY, D.BUY, D.BUY, D.BUY]
    market, evaluations, dates = _build(ohlc, decisions)

    result = run_backtest(market, evaluations)

    assert result.trades == ()
    assert result.open_position is not None
    assert result.open_position.entry_date == dates[1]  # only ever entered once


# ---------------------------------------------------------------------------
# 4/5: BUY BUY BUY NO_SIGNAL -- entry/exit timing and distinct dates
# ---------------------------------------------------------------------------


def test_buy_buy_buy_no_signal_entry_and_exit_timing():
    ohlc = [
        (100.0, 101.0),  # Day1 BUY
        (102.0, 103.0),  # Day2 BUY -> entry here
        (104.0, 105.0),  # Day3 BUY -> remain long
        (106.0, 90.0),  # Day4 NO_SIGNAL -> schedule exit
        (95.0, 96.0),  # Day5 -> exit here
    ]
    decisions = [D.BUY, D.BUY, D.BUY, D.NO_SIGNAL, D.NO_SIGNAL]
    market, evaluations, dates = _build(ohlc, decisions)

    result = run_backtest(market, evaluations)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_signal_date == dates[0]
    assert trade.entry_date == dates[1]
    assert trade.exit_signal_date == dates[3]
    assert trade.exit_date == dates[4]
    assert trade.entry_price == pytest.approx(102.0)
    assert trade.exit_price == pytest.approx(95.0)
    # All four dates are distinct.
    assert len({trade.entry_signal_date, trade.entry_date, trade.exit_signal_date, trade.exit_date}) == 4


# ---------------------------------------------------------------------------
# 6/7: INSUFFICIENT_DATA / FLAT+NO_SIGNAL create no action
# ---------------------------------------------------------------------------


def test_insufficient_data_while_flat_creates_no_action():
    ohlc = [(100.0, 101.0)] * 5
    decisions = [D.INSUFFICIENT_DATA] * 5
    market, evaluations, _ = _build(ohlc, decisions)

    result = run_backtest(market, evaluations)

    assert result.trades == ()
    assert result.open_position is None
    assert result.pending_entry_signal_date is None
    assert all(p.position_quantity == 0 for p in result.equity_curve)


def test_flat_no_signal_creates_no_action():
    ohlc = [(100.0, 101.0)] * 5
    decisions = [D.NO_SIGNAL] * 5
    market, evaluations, _ = _build(ohlc, decisions)

    result = run_backtest(market, evaluations)

    assert result.trades == ()
    assert result.open_position is None
    assert all(p.equity == pytest.approx(p.cash) for p in result.equity_curve)


def test_insufficient_data_while_long_does_not_trigger_exit():
    """INSUFFICIENT_DATA must never trigger any action, even while LONG."""
    ohlc = [(100.0, 101.0), (102.0, 103.0), (104.0, 105.0)]
    decisions = [D.BUY, D.BUY, D.INSUFFICIENT_DATA]
    market, evaluations, dates = _build(ohlc, decisions)

    result = run_backtest(market, evaluations)

    assert result.trades == ()
    assert result.open_position is not None
    assert result.open_position.pending_exit_signal_date is None  # no exit was scheduled


# ---------------------------------------------------------------------------
# 8/9/10: end-of-data censoring (Cases 1, 3, 2)
# ---------------------------------------------------------------------------


def test_buy_on_final_bar_creates_no_fabricated_trade():
    """Case 1: FLAT + BUY on the final bar -- no T+1 OPEN exists."""
    ohlc = [(100.0, 101.0), (102.0, 103.0)]
    decisions = [D.NO_SIGNAL, D.BUY]
    market, evaluations, dates = _build(ohlc, decisions)

    result = run_backtest(market, evaluations)

    assert result.trades == ()
    assert result.open_position is None
    assert result.pending_entry_signal_date == dates[-1]


def test_no_signal_on_final_bar_while_long_does_not_fabricate_exit():
    """Case 3: LONG + NO_SIGNAL on the final bar -- no T+1 OPEN exists."""
    ohlc = [(100.0, 101.0), (102.0, 103.0), (104.0, 90.0)]
    decisions = [D.BUY, D.BUY, D.NO_SIGNAL]
    market, evaluations, dates = _build(ohlc, decisions)

    result = run_backtest(market, evaluations)

    assert result.trades == ()
    assert result.open_position is not None
    assert result.open_position.pending_exit_signal_date == dates[-1]
    assert result.open_position.quantity > 0


def test_open_position_at_end_remains_explicitly_open_no_pending_exit():
    """Case 2: still LONG at the final bar, no exit was ever scheduled."""
    ohlc = [(100.0, 101.0), (102.0, 103.0), (104.0, 105.0)]
    decisions = [D.BUY, D.BUY, D.BUY]
    market, evaluations, dates = _build(ohlc, decisions)

    result = run_backtest(market, evaluations)

    assert result.open_position is not None
    assert result.open_position.pending_exit_signal_date is None
    assert result.pending_entry_signal_date is None


# ---------------------------------------------------------------------------
# 11/12/13: quantity/cash model
# ---------------------------------------------------------------------------


def test_integer_quantity_floors_down():
    ohlc = [(100.0, 101.0), (110.0, 111.0)]
    decisions = [D.BUY, D.BUY]
    market, evaluations, _ = _build(ohlc, decisions)

    result = run_backtest(market, evaluations, BacktestConfig(initial_capital=1000.0))

    assert result.open_position.quantity == 9  # floor(1000/110) = 9.0909... -> 9


def test_cash_never_negative():
    ohlc = [(100.0, 101.0), (99.0, 100.0), (99.0, 100.0), (99.0, 90.0), (80.0, 81.0)]
    decisions = [D.BUY, D.BUY, D.BUY, D.NO_SIGNAL, D.NO_SIGNAL]
    market, evaluations, _ = _build(ohlc, decisions)

    result = run_backtest(market, evaluations, BacktestConfig(initial_capital=1000.0))

    assert all(p.cash >= 0 for p in result.equity_curve)


def test_too_little_capital_for_one_share_creates_no_position():
    ohlc = [(100.0, 101.0), (110.0, 111.0), (112.0, 113.0)]
    decisions = [D.BUY, D.NO_SIGNAL, D.NO_SIGNAL]
    market, evaluations, _ = _build(ohlc, decisions)

    result = run_backtest(market, evaluations, BacktestConfig(initial_capital=50.0))

    assert result.trades == ()
    assert result.open_position is None
    assert result.equity_curve[-1].cash == pytest.approx(50.0)  # untouched


# ---------------------------------------------------------------------------
# 14/15: exact hand-derived closed-trade P&L / return (see manual reference)
# ---------------------------------------------------------------------------
# Covered by test_manual_reference_example_hand_derived above.


# ---------------------------------------------------------------------------
# 16/17: equity definition
# ---------------------------------------------------------------------------


def test_equity_while_flat_equals_cash():
    ohlc = [(100.0, 101.0), (102.0, 103.0)]
    decisions = [D.NO_SIGNAL, D.NO_SIGNAL]
    market, evaluations, _ = _build(ohlc, decisions)

    result = run_backtest(market, evaluations, BacktestConfig(initial_capital=5000.0))

    for point in result.equity_curve:
        assert point.position_quantity == 0
        assert point.position_market_value == 0.0
        assert point.equity == pytest.approx(point.cash)
        assert point.cash == pytest.approx(5000.0)


def test_equity_while_long_equals_cash_plus_quantity_times_close():
    market, evaluations, dates = _manual_reference_fixture()
    result = run_backtest(market, evaluations, BacktestConfig(initial_capital=1000.0))

    day2 = result.equity_curve[1]
    assert day2.position_quantity == 9
    assert day2.position_market_value == pytest.approx(9 * 120.0)
    assert day2.equity == pytest.approx(day2.cash + day2.position_market_value)


# ---------------------------------------------------------------------------
# 18/19: raw OPEN/CLOSE used, never adjusted
# ---------------------------------------------------------------------------


def test_raw_open_used_for_entry_even_when_adjusted_differs():
    market, evaluations, _ = _manual_reference_fixture()
    result = run_backtest(market, evaluations, BacktestConfig(initial_capital=1000.0))
    entry_bar = market.bars[1]
    assert result.trades[0].entry_price == pytest.approx(entry_bar.open)
    assert result.trades[0].entry_price != pytest.approx(entry_bar.adj_close)


def test_raw_close_used_for_equity_even_when_adjusted_differs():
    market, evaluations, _ = _manual_reference_fixture()
    result = run_backtest(market, evaluations, BacktestConfig(initial_capital=1000.0))
    day2_bar = market.bars[1]
    day2_equity = result.equity_curve[1]
    expected_market_value = 9 * day2_bar.close
    assert day2_equity.position_market_value == pytest.approx(expected_market_value)
    assert day2_bar.adj_close != day2_bar.close  # fixture guarantees they differ


# ---------------------------------------------------------------------------
# 20-24: explicit rejection of malformed/misaligned input
# ---------------------------------------------------------------------------


def test_symbol_mismatch_rejected():
    market, evaluations, _ = _manual_reference_fixture()
    bad_evaluations = StrategyEvaluationSeries(
        provider_symbol="OTHER.NS", interval=INTERVAL, strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME,
        evaluations=evaluations.evaluations,
    )
    with pytest.raises(BacktestInputInvalidError):
        run_backtest(market, bad_evaluations)


def test_interval_mismatch_rejected():
    market, evaluations, _ = _manual_reference_fixture()
    bad_evaluations = StrategyEvaluationSeries(
        provider_symbol=SYMBOL, interval="1wk", strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME,
        evaluations=evaluations.evaluations,
    )
    with pytest.raises(BacktestInputInvalidError):
        run_backtest(market, bad_evaluations)


def test_date_alignment_mismatch_rejected():
    market, evaluations, dates = _manual_reference_fixture()
    evals = list(evaluations.evaluations)
    evals[2] = _eval(evals[2].date + timedelta(days=1), evals[2].decision)
    bad_evaluations = StrategyEvaluationSeries(
        provider_symbol=SYMBOL, interval=INTERVAL, strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME, evaluations=tuple(evals)
    )
    with pytest.raises(BacktestInputInvalidError):
        run_backtest(market, bad_evaluations)


def test_length_mismatch_rejected():
    market, evaluations, _ = _manual_reference_fixture()
    bad_evaluations = StrategyEvaluationSeries(
        provider_symbol=SYMBOL, interval=INTERVAL, strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME,
        evaluations=evaluations.evaluations[:-1],
    )
    with pytest.raises(BacktestInputInvalidError):
        run_backtest(market, bad_evaluations)


def test_non_chronological_market_rows_rejected():
    dates = _dates(4)
    bars = [
        _bar(dates[0], 100.0, 101.0),
        _bar(dates[2], 102.0, 103.0),  # out of order vs dates[1] below
        _bar(dates[1], 104.0, 105.0),
        _bar(dates[3], 106.0, 107.0),
    ]
    market = OHLCVSeries(provider_symbol=SYMBOL, interval=INTERVAL, bars=tuple(bars))
    evals = tuple(_eval(b.date, D.NO_SIGNAL) for b in bars)
    evaluations = StrategyEvaluationSeries(
        provider_symbol=SYMBOL, interval=INTERVAL, strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME, evaluations=evals
    )
    with pytest.raises(BacktestInputInvalidError):
        run_backtest(market, evaluations)


def test_nan_price_rejected():
    market, evaluations, dates = _manual_reference_fixture()
    bars = list(market.bars)
    bars[1] = OHLCVBar(date=bars[1].date, open=float("nan"), high=111, low=99, close=105, adj_close=105, volume=1000)
    bad_market = OHLCVSeries(provider_symbol=SYMBOL, interval=INTERVAL, bars=tuple(bars))
    with pytest.raises(BacktestInputInvalidError):
        run_backtest(bad_market, evaluations)


def test_infinite_price_rejected():
    market, evaluations, dates = _manual_reference_fixture()
    bars = list(market.bars)
    bars[2] = OHLCVBar(date=bars[2].date, open=100, high=111, low=99, close=float("inf"), adj_close=105, volume=1000)
    bad_market = OHLCVSeries(provider_symbol=SYMBOL, interval=INTERVAL, bars=tuple(bars))
    with pytest.raises(BacktestInputInvalidError):
        run_backtest(bad_market, evaluations)


def test_non_positive_price_rejected():
    market, evaluations, dates = _manual_reference_fixture()
    bars = list(market.bars)
    bars[0] = OHLCVBar(date=bars[0].date, open=0.0, high=111, low=99, close=105, adj_close=105, volume=1000)
    bad_market = OHLCVSeries(provider_symbol=SYMBOL, interval=INTERVAL, bars=tuple(bars))
    with pytest.raises(BacktestInputInvalidError):
        run_backtest(bad_market, evaluations)


# ---------------------------------------------------------------------------
# 25/26: config validation
# ---------------------------------------------------------------------------


def test_zero_initial_capital_rejected():
    market, evaluations, _ = _manual_reference_fixture()
    with pytest.raises(BacktestInputInvalidError):
        run_backtest(market, evaluations, BacktestConfig(initial_capital=0.0))


def test_negative_initial_capital_rejected():
    market, evaluations, _ = _manual_reference_fixture()
    with pytest.raises(BacktestInputInvalidError):
        run_backtest(market, evaluations, BacktestConfig(initial_capital=-100.0))


def test_nan_initial_capital_rejected():
    market, evaluations, _ = _manual_reference_fixture()
    with pytest.raises(BacktestInputInvalidError):
        run_backtest(market, evaluations, BacktestConfig(initial_capital=float("nan")))


@pytest.mark.parametrize("field", ["transaction_cost", "slippage"])
def test_negative_cost_or_slippage_rejected(field):
    market, evaluations, _ = _manual_reference_fixture()
    with pytest.raises(BacktestInputInvalidError):
        run_backtest(market, evaluations, BacktestConfig(**{field: -0.001}))


@pytest.mark.parametrize("field", ["transaction_cost", "slippage"])
def test_nonzero_cost_or_slippage_rejected_v1(field):
    """Phase 2B V1 defines no cost/slippage model -- a nonzero value must be
    rejected explicitly, never silently ignored (would be misleading)."""
    market, evaluations, _ = _manual_reference_fixture()
    with pytest.raises(BacktestInputInvalidError):
        run_backtest(market, evaluations, BacktestConfig(**{field: 0.001}))


def test_default_config_is_valid():
    market, evaluations, _ = _manual_reference_fixture()
    result = run_backtest(market, evaluations, BacktestConfig())
    assert result.config.initial_capital == pytest.approx(100_000.0)
    assert result.config.transaction_cost == 0.0
    assert result.config.slippage == 0.0


# ---------------------------------------------------------------------------
# 27/28: non-mutation, determinism
# ---------------------------------------------------------------------------


def test_no_input_mutation():
    market, evaluations, _ = _manual_reference_fixture()
    market_before = copy.deepcopy(market)
    evaluations_before = copy.deepcopy(evaluations)

    run_backtest(market, evaluations, BacktestConfig(initial_capital=1000.0))

    assert market == market_before
    assert evaluations == evaluations_before


def test_deterministic_repeated_execution():
    market, evaluations, _ = _manual_reference_fixture()
    config = BacktestConfig(initial_capital=1000.0)

    result_a = run_backtest(market, evaluations, config)
    result_b = run_backtest(market, evaluations, config)

    assert result_a == result_b


# ---------------------------------------------------------------------------
# 29: strict no-look-ahead
# ---------------------------------------------------------------------------


def test_changing_t_plus_1_open_changes_the_fill():
    ohlc_a = [(100.0, 101.0), (110.0, 111.0)]
    ohlc_b = [(100.0, 101.0), (200.0, 201.0)]  # only T+1 OPEN differs
    decisions = [D.BUY, D.NO_SIGNAL]

    market_a, evaluations, dates = _build(ohlc_a, decisions)
    market_b, _, _ = _build(ohlc_b, decisions, dates=dates)

    result_a = run_backtest(market_a, evaluations, BacktestConfig(initial_capital=10_000.0))
    result_b = run_backtest(market_b, evaluations, BacktestConfig(initial_capital=10_000.0))

    assert result_a.open_position.entry_price == pytest.approx(110.0)
    assert result_b.open_position.entry_price == pytest.approx(200.0)
    assert result_a.open_position.entry_price != result_b.open_position.entry_price


def test_prices_after_completed_trade_never_change_it():
    """Changing prices strictly after a trade has fully closed must never
    retroactively change that trade's entry/exit decision or fill."""
    ohlc_a = [
        (100.0, 101.0),  # BUY
        (110.0, 111.0),  # entry here
        (112.0, 90.0),  # NO_SIGNAL -> schedule exit
        (95.0, 96.0),  # exit here -- trade fully closed after this bar
        (97.0, 98.0),  # untouched tail (identical in both variants)
    ]
    decisions = [D.BUY, D.BUY, D.NO_SIGNAL, D.NO_SIGNAL, D.NO_SIGNAL]
    market_a, evaluations, dates = _build(ohlc_a, decisions)

    ohlc_b = list(ohlc_a)
    ohlc_b[4] = (9999.0, 1.0)  # wildly different AFTER the trade closed
    market_b, _, _ = _build(ohlc_b, decisions, dates=dates)

    result_a = run_backtest(market_a, evaluations, BacktestConfig(initial_capital=1000.0))
    result_b = run_backtest(market_b, evaluations, BacktestConfig(initial_capital=1000.0))

    assert result_a.trades == result_b.trades


def test_t_open_never_used_for_buy_generated_from_t_close():
    """A BUY decision observed at bar T (based on T's Close) must never be
    filled at T's own OPEN."""
    ohlc = [(500.0, 101.0), (110.0, 111.0)]  # T's OPEN (500) is a decoy
    decisions = [D.BUY, D.NO_SIGNAL]
    market, evaluations, dates = _build(ohlc, decisions)

    result = run_backtest(market, evaluations, BacktestConfig(initial_capital=10_000.0))

    assert result.open_position.entry_price == pytest.approx(110.0)
    assert result.open_position.entry_price != pytest.approx(500.0)


# ---------------------------------------------------------------------------
# Result identity
# ---------------------------------------------------------------------------


def test_backtest_result_identity_fields():
    market, evaluations, _ = _manual_reference_fixture()
    result = run_backtest(market, evaluations)

    assert isinstance(result, BacktestResult)
    assert result.provider_symbol == SYMBOL
    assert result.interval == INTERVAL
    assert result.strategy_id == STRATEGY_ID
    assert result.strategy_name == STRATEGY_NAME

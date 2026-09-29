"""Phase 2A: historical signal outcome engine tests.

Market series used throughout: close[i] = 100 + i, high[i] = close[i] + 5,
low[i] = close[i] - 5 — a simple, hand-verifiable linear series. Dates use
deliberately irregular gaps (simulating weekends/holidays) to prove all
+5D/+10D/MAE/MFE counting is strictly by trading-bar INDEX, never by
calendar-day arithmetic.
"""

import copy
from datetime import date, timedelta

import pytest

from app.core.exceptions import OutcomeInputInvalidError
from app.market_data.models import OHLCVBar, OHLCVSeries
from app.outcomes.engine import compute_signal_outcomes
from app.outcomes.models import SignalOutcomeSeries
from app.strategies.models import StrategyDecision, StrategyEvaluation, StrategyEvaluationSeries

SYMBOL = "X.NS"
INTERVAL = "1d"
STRATEGY_ID = "trend_momentum_v1"
STRATEGY_NAME = "Trend + Momentum v1"

# Irregular day-gap pattern (weekend/holiday-like), reused/extended as needed.
_GAPS = [1, 1, 3, 1, 3, 1, 1, 3, 1, 3, 1, 1, 3, 1, 3, 1, 1, 3, 1, 3, 1, 1]


def _dates(n: int, start: date = date(2024, 1, 1)) -> list[date]:
    dates = [start]
    for i in range(n - 1):
        dates.append(dates[-1] + timedelta(days=_GAPS[i % len(_GAPS)]))
    return dates


def _bar(d: date, close: float) -> OHLCVBar:
    return OHLCVBar(date=d, open=close, high=close + 5, low=close - 5, close=close, adj_close=close, volume=1000)


def _market(n: int, symbol: str = SYMBOL, interval: str = INTERVAL) -> OHLCVSeries:
    dates = _dates(n)
    bars = tuple(_bar(d, 100.0 + i) for i, d in enumerate(dates))
    return OHLCVSeries(provider_symbol=symbol, interval=interval, bars=bars)


def _evaluation(d: date, decision: StrategyDecision) -> StrategyEvaluation:
    return StrategyEvaluation(
        date=d, strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME, decision=decision, conditions=(), missing_inputs=()
    )


def _evaluations(market: OHLCVSeries, buy_indices: set[int], symbol: str = SYMBOL, interval: str = INTERVAL) -> StrategyEvaluationSeries:
    evals = tuple(
        _evaluation(bar.date, StrategyDecision.BUY if i in buy_indices else StrategyDecision.NO_SIGNAL)
        for i, bar in enumerate(market.bars)
    )
    return StrategyEvaluationSeries(provider_symbol=symbol, interval=interval, strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME, evaluations=evals)


# ---------------------------------------------------------------------------
# A/B/C/D/E/F/G/H/I: indexing, hand-derived returns, MAE/MFE correctness
# ---------------------------------------------------------------------------


def test_full_window_outcome_hand_derived_values():
    """BUY with >=10 future bars: +5D, +10D, MAE, MFE all present and exact."""
    market = _market(20)
    evaluations = _evaluations(market, buy_indices={5})

    result = compute_signal_outcomes(market, evaluations)

    assert len(result.outcomes) == 1
    outcome = result.outcomes[0]

    reference_close = 105.0  # close[5] = 100 + 5
    forward_close_5d = 110.0  # close[10] = 100 + 10 -- exact +5 TRADING-BAR index
    forward_close_10d = 115.0  # close[15] = 100 + 15 -- exact +10 TRADING-BAR index

    assert outcome.reference_close == pytest.approx(reference_close)
    assert outcome.forward_close_5d == pytest.approx(forward_close_5d)
    assert outcome.forward_return_5d == pytest.approx(forward_close_5d / reference_close - 1)
    assert outcome.forward_close_10d == pytest.approx(forward_close_10d)
    assert outcome.forward_return_10d == pytest.approx(forward_close_10d / reference_close - 1)

    # Window = bars[6:16] (signal bar at index 5 excluded). low[j] = 95+j,
    # high[j] = 105+j -> min low at j=6 (101), max high at j=15 (120).
    min_low = 101.0
    max_high = 120.0
    assert outcome.mae_10d == pytest.approx(min_low / reference_close - 1)
    assert outcome.mfe_10d == pytest.approx(max_high / reference_close - 1)
    assert outcome.available_forward_bars == 14  # 20 - 1 - 5


def test_signal_bar_excluded_from_mae_mfe_window():
    """H: the signal bar's own low/high must never enter the MAE/MFE window."""
    market = _market(20)
    # Make the signal bar's low/high extreme outliers that would dominate
    # min/max if (incorrectly) included in the window.
    bars = list(market.bars)
    signal_bar = bars[5]
    bars[5] = OHLCVBar(
        date=signal_bar.date, open=signal_bar.open, high=10_000.0, low=-10_000.0,
        close=signal_bar.close, adj_close=signal_bar.close, volume=signal_bar.volume,
    )
    market = OHLCVSeries(provider_symbol=SYMBOL, interval=INTERVAL, bars=tuple(bars))
    evaluations = _evaluations(market, buy_indices={5})

    outcome = compute_signal_outcomes(market, evaluations).outcomes[0]

    assert outcome.mae_10d == pytest.approx(101.0 / 105.0 - 1)
    assert outcome.mfe_10d == pytest.approx(120.0 / 105.0 - 1)


def test_weekend_holiday_gaps_do_not_affect_bar_counting():
    """C: identical index-based outcome regardless of calendar-day gaps."""
    market_irregular = _market(20)  # irregular gaps via _dates
    dates_regular = [date(2024, 1, 1) + timedelta(days=i) for i in range(20)]
    bars_regular = tuple(_bar(d, 100.0 + i) for i, d in enumerate(dates_regular))
    market_regular = OHLCVSeries(provider_symbol=SYMBOL, interval=INTERVAL, bars=bars_regular)

    outcome_irregular = compute_signal_outcomes(market_irregular, _evaluations(market_irregular, {5})).outcomes[0]
    outcome_regular = compute_signal_outcomes(market_regular, _evaluations(market_regular, {5})).outcomes[0]

    assert outcome_irregular.forward_return_5d == pytest.approx(outcome_regular.forward_return_5d)
    assert outcome_irregular.forward_return_10d == pytest.approx(outcome_regular.forward_return_10d)
    assert outcome_irregular.mae_10d == pytest.approx(outcome_regular.mae_10d)
    assert outcome_irregular.mfe_10d == pytest.approx(outcome_regular.mfe_10d)


# ---------------------------------------------------------------------------
# J/K/L/M: end-of-data censoring
# ---------------------------------------------------------------------------


def test_buy_with_exactly_10_future_bars():
    """J: signal with exactly 10 future bars -- everything available."""
    n = 16  # signal at index 5, future bars = indices 6..15 = 10 bars
    market = _market(n)
    outcome = compute_signal_outcomes(market, _evaluations(market, {5})).outcomes[0]

    assert outcome.available_forward_bars == 10
    assert outcome.forward_close_5d is not None
    assert outcome.forward_close_10d is not None
    assert outcome.mae_10d is not None
    assert outcome.mfe_10d is not None


def test_buy_with_exactly_5_future_bars():
    """K: 5D available, 10D and 10D MAE/MFE unavailable."""
    n = 11  # signal at index 5, future bars = indices 6..10 = 5 bars
    market = _market(n)
    outcome = compute_signal_outcomes(market, _evaluations(market, {5})).outcomes[0]

    assert outcome.available_forward_bars == 5
    assert outcome.forward_close_5d == pytest.approx(110.0)
    assert outcome.forward_return_5d == pytest.approx(110.0 / 105.0 - 1)
    assert outcome.forward_close_10d is None
    assert outcome.forward_return_10d is None
    assert outcome.mae_10d is None
    assert outcome.mfe_10d is None


def test_buy_with_4_future_bars():
    """L: fewer than 5 future bars -- 5D and 10D both unavailable."""
    n = 10  # signal at index 5, future bars = indices 6..9 = 4 bars
    market = _market(n)
    outcome = compute_signal_outcomes(market, _evaluations(market, {5})).outcomes[0]

    assert outcome.available_forward_bars == 4
    assert outcome.forward_close_5d is None
    assert outcome.forward_return_5d is None
    assert outcome.forward_close_10d is None
    assert outcome.forward_return_10d is None
    assert outcome.mae_10d is None
    assert outcome.mfe_10d is None


def test_buy_on_final_row():
    """M: signal on the very last row -- preserved, all metrics unavailable."""
    n = 6
    market = _market(n)
    outcome = compute_signal_outcomes(market, _evaluations(market, {5})).outcomes[0]

    assert outcome.date == market.bars[5].date
    assert outcome.reference_close == pytest.approx(105.0)
    assert outcome.available_forward_bars == 0
    assert outcome.forward_close_5d is None
    assert outcome.forward_close_10d is None
    assert outcome.mae_10d is None
    assert outcome.mfe_10d is None


def test_never_drops_or_shortens_censored_signal():
    """9: a censored signal is preserved, not dropped, invented, or shortened
    into a partial 10D measurement presented as full."""
    n = 9  # 3 future bars only
    market = _market(n)
    outcome = compute_signal_outcomes(market, _evaluations(market, {5})).outcomes[0]

    assert outcome is not None
    assert outcome.available_forward_bars == 3
    assert outcome.mae_10d is None  # never a partial 3-bar MAE mislabeled as 10D
    assert outcome.mfe_10d is None


# ---------------------------------------------------------------------------
# N/O/P/Q: population rules
# ---------------------------------------------------------------------------


def test_no_signal_produces_no_outcome():
    market = _market(20)
    evaluations = _evaluations(market, buy_indices=set())  # all NO_SIGNAL
    result = compute_signal_outcomes(market, evaluations)
    assert result.outcomes == ()


def test_insufficient_data_produces_no_outcome():
    market = _market(20)
    evals = tuple(
        _evaluation(bar.date, StrategyDecision.INSUFFICIENT_DATA if i < 5 else StrategyDecision.NO_SIGNAL)
        for i, bar in enumerate(market.bars)
    )
    evaluations = StrategyEvaluationSeries(
        provider_symbol=SYMBOL, interval=INTERVAL, strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME, evaluations=evals
    )
    result = compute_signal_outcomes(market, evaluations)
    assert result.outcomes == ()


def test_multiple_buy_signals_handled_independently():
    market = _market(25)
    evaluations = _evaluations(market, buy_indices={3, 12})
    result = compute_signal_outcomes(market, evaluations)

    assert len(result.outcomes) == 2
    first, second = result.outcomes
    assert first.date == market.bars[3].date
    assert second.date == market.bars[12].date
    assert first.reference_close == pytest.approx(103.0)
    assert second.reference_close == pytest.approx(112.0)


def test_consecutive_buy_evaluations_preserved_separately():
    """Q: consecutive BUY states are NOT collapsed in Phase 2A."""
    market = _market(20)
    evaluations = _evaluations(market, buy_indices={5, 6, 7, 8})
    result = compute_signal_outcomes(market, evaluations)

    assert len(result.outcomes) == 4
    assert [o.date for o in result.outcomes] == [market.bars[i].date for i in (5, 6, 7, 8)]
    # Each has its own independent reference_close.
    assert [o.reference_close for o in result.outcomes] == [105.0, 106.0, 107.0, 108.0]


# ---------------------------------------------------------------------------
# R/S/T: reference price policy, determinism, non-mutation
# ---------------------------------------------------------------------------


def test_raw_close_used_not_adjusted_close():
    """R: reference_close must equal the raw close, even when adj_close differs."""
    dates = _dates(10)
    bars = tuple(
        OHLCVBar(date=d, open=100.0 + i, high=105.0 + i, low=95.0 + i, close=100.0 + i, adj_close=(100.0 + i) * 0.9, volume=1000)
        for i, d in enumerate(dates)
    )
    market = OHLCVSeries(provider_symbol=SYMBOL, interval=INTERVAL, bars=bars)
    evaluations = _evaluations(market, buy_indices={2})

    outcome = compute_signal_outcomes(market, evaluations).outcomes[0]

    assert outcome.reference_close == pytest.approx(102.0)  # raw close, not adj_close (91.8)


def test_deterministic_repeated_execution():
    """S: identical input produces byte-identical output across repeated calls."""
    market = _market(20)
    evaluations = _evaluations(market, buy_indices={5, 10})

    result_a = compute_signal_outcomes(market, evaluations)
    result_b = compute_signal_outcomes(market, evaluations)

    assert result_a == result_b


def test_no_input_mutation():
    """T: inputs are never mutated by the engine."""
    market = _market(20)
    evaluations = _evaluations(market, buy_indices={5, 10})
    market_before = copy.deepcopy(market)
    evaluations_before = copy.deepcopy(evaluations)

    compute_signal_outcomes(market, evaluations)

    assert market == market_before
    assert evaluations == evaluations_before


# ---------------------------------------------------------------------------
# U/V/W/X: explicit rejection of malformed/misaligned input
# ---------------------------------------------------------------------------


def test_non_finite_close_rejected():
    dates = _dates(10)
    bars = list(_bar(d, 100.0 + i) for i, d in enumerate(dates))
    bars[7] = OHLCVBar(date=dates[7], open=100, high=110, low=90, close=float("nan"), adj_close=100, volume=1000)
    market = OHLCVSeries(provider_symbol=SYMBOL, interval=INTERVAL, bars=tuple(bars))
    evaluations = _evaluations(market, buy_indices={2})

    with pytest.raises(OutcomeInputInvalidError):
        compute_signal_outcomes(market, evaluations)


def test_symbol_mismatch_rejected():
    market = _market(10)
    evaluations = _evaluations(market, buy_indices={2}, symbol="OTHER.NS")

    with pytest.raises(OutcomeInputInvalidError):
        compute_signal_outcomes(market, evaluations)


def test_interval_mismatch_rejected():
    market = _market(10)
    evaluations = _evaluations(market, buy_indices={2}, interval="1wk")

    with pytest.raises(OutcomeInputInvalidError):
        compute_signal_outcomes(market, evaluations)


def test_date_alignment_mismatch_rejected():
    market = _market(10)
    evaluations = _evaluations(market, buy_indices={2})
    # Shift one evaluation's date so it no longer matches its market bar.
    evals = list(evaluations.evaluations)
    shifted = evals[4]
    evals[4] = _evaluation(shifted.date + timedelta(days=1), shifted.decision)
    evaluations = StrategyEvaluationSeries(
        provider_symbol=SYMBOL, interval=INTERVAL, strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME, evaluations=tuple(evals)
    )

    with pytest.raises(OutcomeInputInvalidError):
        compute_signal_outcomes(market, evaluations)


def test_row_count_mismatch_rejected():
    market = _market(10)
    evaluations = _evaluations(market, buy_indices={2})
    truncated = StrategyEvaluationSeries(
        provider_symbol=SYMBOL, interval=INTERVAL, strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME,
        evaluations=evaluations.evaluations[:-1],
    )

    with pytest.raises(OutcomeInputInvalidError):
        compute_signal_outcomes(market, truncated)


# ---------------------------------------------------------------------------
# 12: strict no-look-ahead boundary test
# ---------------------------------------------------------------------------


def test_outcome_unaffected_by_prices_beyond_its_own_horizon():
    """Changing bars strictly beyond a signal's 10-bar horizon must never
    change that signal's own outcome -- the engine must not look further
    ahead than its declared window."""
    market_a = _market(30)
    evaluations = _evaluations(market_a, buy_indices={5})

    bars_b = list(market_a.bars)
    # Mutate every bar from index 16 onward (beyond signal 5's +10D bar at
    # index 15) to wildly different prices.
    for j in range(16, len(bars_b)):
        d = bars_b[j].date
        bars_b[j] = OHLCVBar(date=d, open=9999, high=9999, low=1, close=9999, adj_close=9999, volume=1)
    market_b = OHLCVSeries(provider_symbol=SYMBOL, interval=INTERVAL, bars=tuple(bars_b))

    outcome_a = compute_signal_outcomes(market_a, evaluations).outcomes[0]
    outcome_b = compute_signal_outcomes(market_b, evaluations).outcomes[0]

    assert outcome_a == outcome_b


def test_mae_can_be_positive_and_mfe_can_be_negative():
    """14: MAE/MFE sign must follow the actual data, not an assumed sign --
    if the whole future window trades above reference, MAE is positive."""
    n = 16
    dates = _dates(n)
    # Every future bar's low/high stays comfortably ABOVE the reference close.
    bars = [_bar(dates[0], 100.0)] + [
        OHLCVBar(date=dates[i], open=150.0, high=160.0, low=150.0, close=150.0, adj_close=150.0, volume=1000)
        for i in range(1, n)
    ]
    market = OHLCVSeries(provider_symbol=SYMBOL, interval=INTERVAL, bars=tuple(bars))
    evaluations = _evaluations(market, buy_indices={0})

    outcome = compute_signal_outcomes(market, evaluations).outcomes[0]

    assert outcome.mae_10d > 0  # even the worst future low is above reference
    assert outcome.mfe_10d > 0
    assert outcome.mae_10d <= outcome.mfe_10d


def test_signal_outcome_series_identity_fields():
    market = _market(10)
    evaluations = _evaluations(market, buy_indices={2})
    result = compute_signal_outcomes(market, evaluations)

    assert isinstance(result, SignalOutcomeSeries)
    assert result.provider_symbol == SYMBOL
    assert result.interval == INTERVAL
    assert result.strategy_id == STRATEGY_ID
    assert result.strategy_name == STRATEGY_NAME

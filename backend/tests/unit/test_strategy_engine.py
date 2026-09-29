import copy
from collections import Counter
from datetime import date, timedelta

import pytest

from app.core.exceptions import StrategyInputInvalidError
from app.indicators.engine import compute_indicators
from app.indicators.models import IndicatorRow, IndicatorSeries
from app.market_data.models import OHLCVBar, OHLCVSeries
from app.strategies.engine import evaluate_strategy
from app.strategies.models import StrategyDecision


def _make_market_series(n=60, start=date(2024, 1, 1), symbol="X.NS", interval="1d", close_fn=None):
    bars = []
    close = 100.0
    for i in range(n):
        if close_fn is not None:
            close = close_fn(i, close)
        else:
            close += 1.0 if i % 2 == 0 else -0.5
        d = start + timedelta(days=i)
        bars.append(
            OHLCVBar(date=d, open=close - 1, high=close + 2, low=close - 2, close=close,
                     adj_close=close, volume=1000 + i)
        )
    return OHLCVSeries(provider_symbol=symbol, interval=interval, bars=tuple(bars))


def _trend_reversal_close_fn(i, close):
    if i < 50:
        return close + 0.01
    elif i < 65:
        return close + 3.0
    return close - 3.0


# ---------------------------------------------------------------------------
# Series-level identity, length, alignment (happy path)
# ---------------------------------------------------------------------------


def test_evaluate_strategy_length_and_identity():
    market = _make_market_series(n=60)
    indicators = compute_indicators(market)

    result = evaluate_strategy(market, indicators)

    assert len(result.evaluations) == len(market.bars) == len(indicators.rows)
    assert result.provider_symbol == "X.NS"
    assert result.interval == "1d"
    assert result.strategy_id == "trend_momentum_v1"
    assert result.strategy_name == "Trend + Momentum v1"
    assert all(e.strategy_id == "trend_momentum_v1" for e in result.evaluations)
    assert all(e.strategy_name == "Trend + Momentum v1" for e in result.evaluations)
    assert [e.date for e in result.evaluations] == [b.date for b in market.bars]


def test_no_insufficient_data_rows_are_skipped():
    market = _make_market_series(n=60)
    indicators = compute_indicators(market)
    result = evaluate_strategy(market, indicators)
    # warm-up rows must still be present, not omitted
    assert result.evaluations[0].decision is StrategyDecision.INSUFFICIENT_DATA


# ---------------------------------------------------------------------------
# Alignment failures
# ---------------------------------------------------------------------------


def test_symbol_mismatch_raises():
    market = _make_market_series(n=20, symbol="A.NS")
    indicators = compute_indicators(_make_market_series(n=20, symbol="B.NS"))
    with pytest.raises(StrategyInputInvalidError):
        evaluate_strategy(market, indicators)


def test_interval_mismatch_raises():
    market = _make_market_series(n=20, interval="1d")
    bad_indicators = IndicatorSeries(
        provider_symbol=market.provider_symbol,
        interval="1wk",
        rows=tuple(IndicatorRow(date=b.date, sma20=None, sma50=None, rsi14=None,
                                 average_volume=None, volume_ratio=None) for b in market.bars),
    )
    with pytest.raises(StrategyInputInvalidError):
        evaluate_strategy(market, bad_indicators)


def test_length_mismatch_raises():
    market = _make_market_series(n=20)
    short_indicators = compute_indicators(_make_market_series(n=15, symbol=market.provider_symbol))
    with pytest.raises(StrategyInputInvalidError):
        evaluate_strategy(market, short_indicators)


def test_date_mismatch_same_length_raises():
    market = _make_market_series(n=20)
    indicators = compute_indicators(market)
    # shift one row's date by a day, keeping length identical
    rows = list(indicators.rows)
    shifted = rows[5]
    rows[5] = IndicatorRow(
        date=shifted.date + timedelta(days=1),
        sma20=shifted.sma20, sma50=shifted.sma50, rsi14=shifted.rsi14,
        average_volume=shifted.average_volume, volume_ratio=shifted.volume_ratio,
    )
    bad_indicators = IndicatorSeries(indicators.provider_symbol, indicators.interval, tuple(rows))

    with pytest.raises(StrategyInputInvalidError):
        evaluate_strategy(market, bad_indicators)


def test_ordering_mismatch_raises():
    market = _make_market_series(n=10)
    indicators = compute_indicators(market)
    reordered_rows = tuple(reversed(indicators.rows))
    bad_indicators = IndicatorSeries(indicators.provider_symbol, indicators.interval, reordered_rows)

    with pytest.raises(StrategyInputInvalidError):
        evaluate_strategy(market, bad_indicators)


# ---------------------------------------------------------------------------
# No-look-ahead (end-to-end pipeline: OHLCV -> Phase 1C -> Phase 1D)
# ---------------------------------------------------------------------------


def test_no_look_ahead_end_to_end_pipeline():
    market = _make_market_series(n=90, close_fn=_trend_reversal_close_fn)
    indicators = compute_indicators(market)
    result_before = evaluate_strategy(market, indicators)

    # Sanity: this fixture naturally exercises all three decisions.
    decision_counts = Counter(e.decision for e in result_before.evaluations)
    assert decision_counts[StrategyDecision.INSUFFICIENT_DATA] > 0
    assert decision_counts[StrategyDecision.BUY] > 0
    assert decision_counts[StrategyDecision.NO_SIGNAL] > 0

    future_bars = list(market.bars) + [
        OHLCVBar(date=market.bars[-1].date + timedelta(days=i + 1),
                 open=99999, high=100000, low=90000, close=99999, adj_close=99999, volume=1)
        for i in range(10)
    ]
    extended_market = OHLCVSeries(market.provider_symbol, market.interval, tuple(future_bars))
    extended_indicators = compute_indicators(extended_market)
    result_after = evaluate_strategy(extended_market, extended_indicators)

    for i in range(len(market.bars)):
        assert result_after.evaluations[i] == result_before.evaluations[i]


# ---------------------------------------------------------------------------
# Non-mutation
# ---------------------------------------------------------------------------


def test_does_not_mutate_inputs():
    market = _make_market_series(n=60)
    indicators = compute_indicators(market)
    market_snapshot = copy.deepcopy(market)
    indicators_snapshot = copy.deepcopy(indicators)

    evaluate_strategy(market, indicators)

    assert market == market_snapshot
    assert indicators == indicators_snapshot


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_deterministic_repeated_series_evaluation():
    market = _make_market_series(n=60)
    indicators = compute_indicators(market)

    result1 = evaluate_strategy(market, indicators)
    result2 = evaluate_strategy(market, indicators)

    assert result1 == result2

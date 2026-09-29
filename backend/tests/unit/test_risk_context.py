"""Phase 3B: deterministic point-in-time risk context & market regime tests."""

import copy
import math
import statistics
from datetime import date, timedelta

import pytest

from app.audit.engine import build_risk_market_context
from app.audit.models import Comparison, MarketRegime
from app.core.exceptions import StrategyAuditInputInvalidError
from app.indicators.models import IndicatorRow, IndicatorSeries
from app.market_data.models import OHLCVBar, OHLCVSeries

SYMBOL = "X.NS"
INTERVAL = "1d"

_GAPS = [1, 1, 3, 1, 3, 1, 1, 3, 1, 3, 1, 1, 3, 1, 3, 1, 1, 3, 1, 3, 1, 1, 3, 1, 3, 1, 1, 3, 1, 3]


def _dates(n: int, start: date = date(2024, 1, 1)) -> list[date]:
    dates = [start]
    for i in range(n - 1):
        dates.append(dates[-1] + timedelta(days=_GAPS[i % len(_GAPS)]))
    return dates


def _bar(d: date, close: float, adj_close: float | None = None) -> OHLCVBar:
    adj_close = close if adj_close is None else adj_close
    return OHLCVBar(date=d, open=close, high=close + 5, low=close - 5, close=close, adj_close=adj_close, volume=1000)


def _row(d: date, sma20: float | None, sma50: float | None) -> IndicatorRow:
    return IndicatorRow(date=d, sma20=sma20, sma50=sma50, rsi14=None, average_volume=None, volume_ratio=None)


def _build(closes, sma20s, sma50s, adj_closes=None, symbol=SYMBOL, interval=INTERVAL):
    dates = _dates(len(closes))
    adj_closes = adj_closes or closes
    bars = tuple(_bar(d, c, a) for d, c, a in zip(dates, closes, adj_closes))
    market = OHLCVSeries(provider_symbol=symbol, interval=interval, bars=bars)
    rows = tuple(_row(d, s20, s50) for d, s20, s50 in zip(dates, sma20s, sma50s))
    indicators = IndicatorSeries(provider_symbol=symbol, interval=interval, rows=rows)
    return market, indicators, dates


# ---------------------------------------------------------------------------
# Volatility: A-H
# ---------------------------------------------------------------------------


def test_A_exactly_21_closes_hand_derived():
    closes = [100.0 + i for i in range(21)]  # 21 closes, audit at index 20
    market, indicators, dates = _build(closes, [None] * 21, [None] * 21)
    audit_date = dates[20]

    returns = [closes[k] / closes[k - 1] - 1 for k in range(1, 21)]
    expected = statistics.stdev(returns) * math.sqrt(252)

    context = build_risk_market_context(market, indicators, audit_date)
    assert context.annualized_realized_volatility_20 == pytest.approx(expected)


def test_B_only_20_closes_gives_none():
    closes = [100.0 + i for i in range(20)]  # only 20 -> insufficient for 21-close window
    market, indicators, dates = _build(closes, [None] * 20, [None] * 20)
    audit_date = dates[19]

    context = build_risk_market_context(market, indicators, audit_date)
    assert context.annualized_realized_volatility_20 is None


def test_C_more_than_21_closes_uses_only_final_21():
    # Leading bars (indices 0..4) have wildly different prices; the final
    # 21 closes (indices 5..25) match test_A's fixture exactly.
    leading = [9999.0, 1.0, 5000.0, 50.0, 7777.0]
    tail = [100.0 + i for i in range(21)]
    closes = leading + tail
    market, indicators, dates = _build(closes, [None] * len(closes), [None] * len(closes))
    audit_date = dates[25]  # index of the last tail close

    returns = [tail[k] / tail[k - 1] - 1 for k in range(1, 21)]
    expected = statistics.stdev(returns) * math.sqrt(252)

    context = build_risk_market_context(market, indicators, audit_date)
    assert context.annualized_realized_volatility_20 == pytest.approx(expected)


def test_D_constant_closes_gives_exact_zero_not_none():
    closes = [100.0] * 21
    market, indicators, dates = _build(closes, [None] * 21, [None] * 21)
    audit_date = dates[20]

    context = build_risk_market_context(market, indicators, audit_date)
    assert context.annualized_realized_volatility_20 == pytest.approx(0.0)
    assert context.annualized_realized_volatility_20 is not None


def test_E_uses_raw_close_never_adjusted_close():
    closes = [100.0 + i for i in range(21)]
    adj_closes = [c * 0.5 for c in closes]  # drastically different
    market, indicators, dates = _build(closes, [None] * 21, [None] * 21, adj_closes=adj_closes)
    audit_date = dates[20]

    returns = [closes[k] / closes[k - 1] - 1 for k in range(1, 21)]
    expected = statistics.stdev(returns) * math.sqrt(252)

    context = build_risk_market_context(market, indicators, audit_date)
    assert context.annualized_realized_volatility_20 == pytest.approx(expected)


def test_F_uses_sample_stdev_ddof1_not_population():
    closes = [100.0, 103.0, 98.0, 107.0, 95.0, 110.0, 101.0, 99.0, 115.0, 90.0,
              105.0, 100.0, 108.0, 96.0, 112.0, 97.0, 103.0, 100.0, 106.0, 94.0, 109.0]
    market, indicators, dates = _build(closes, [None] * 21, [None] * 21)
    audit_date = dates[20]

    returns = [closes[k] / closes[k - 1] - 1 for k in range(1, 21)]
    sample_expected = statistics.stdev(returns) * math.sqrt(252)
    population_alternative = statistics.pstdev(returns) * math.sqrt(252)
    assert sample_expected != pytest.approx(population_alternative)

    context = build_risk_market_context(market, indicators, audit_date)
    assert context.annualized_realized_volatility_20 == pytest.approx(sample_expected)


def test_G_uses_simple_returns_not_log_returns():
    closes = [100.0, 103.0, 98.0, 107.0, 95.0, 110.0, 101.0, 99.0, 115.0, 90.0,
              105.0, 100.0, 108.0, 96.0, 112.0, 97.0, 103.0, 100.0, 106.0, 94.0, 109.0]
    market, indicators, dates = _build(closes, [None] * 21, [None] * 21)
    audit_date = dates[20]

    simple_returns = [closes[k] / closes[k - 1] - 1 for k in range(1, 21)]
    log_returns = [math.log(closes[k] / closes[k - 1]) for k in range(1, 21)]
    simple_expected = statistics.stdev(simple_returns) * math.sqrt(252)
    log_alternative = statistics.stdev(log_returns) * math.sqrt(252)
    assert simple_expected != pytest.approx(log_alternative)

    context = build_risk_market_context(market, indicators, audit_date)
    assert context.annualized_realized_volatility_20 == pytest.approx(simple_expected)


def test_H_audit_date_in_middle_excludes_future_prices():
    closes_a = [100.0 + i for i in range(30)]
    market_a, indicators_a, dates_a = _build(closes_a, [None] * 30, [None] * 30)
    audit_date = dates_a[25]

    closes_b = list(closes_a)
    for j in range(26, 30):
        closes_b[j] = 999999.0
    market_b, indicators_b, dates_b = _build(closes_b, [None] * 30, [None] * 30)
    assert dates_b == dates_a

    context_a = build_risk_market_context(market_a, indicators_a, audit_date)
    context_b = build_risk_market_context(market_b, indicators_b, audit_date)
    assert context_a.annualized_realized_volatility_20 == context_b.annualized_realized_volatility_20


# ---------------------------------------------------------------------------
# Regime truth table: A-H
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "close,sma20,sma50,expected",
    [
        (110.0, 105.0, 100.0, MarketRegime.BULLISH_TREND),  # A: close > sma20 > sma50
        (90.0, 95.0, 100.0, MarketRegime.BEARISH_TREND),  # B: close < sma20 < sma50
        (110.0, 105.0, 108.0, MarketRegime.TRANSITIONAL),  # C: close > sma20, sma20 < sma50
        (90.0, 95.0, 92.0, MarketRegime.TRANSITIONAL),  # D: close < sma20, sma20 > sma50
        (100.0, 100.0, 95.0, MarketRegime.TRANSITIONAL),  # E: close == sma20
        (105.0, 100.0, 100.0, MarketRegime.TRANSITIONAL),  # F: sma20 == sma50
    ],
)
def test_regime_truth_table(close, sma20, sma50, expected):
    closes = [close]
    market, indicators, dates = _build(closes, [sma20], [sma50])
    context = build_risk_market_context(market, indicators, dates[0])
    assert context.regime == expected


def test_regime_evidence_comparisons_match_classification():
    closes = [110.0]
    market, indicators, dates = _build(closes, [105.0], [100.0])
    context = build_risk_market_context(market, indicators, dates[0])
    assert context.regime_evidence.close == pytest.approx(110.0)
    assert context.regime_evidence.sma20 == pytest.approx(105.0)
    assert context.regime_evidence.sma50 == pytest.approx(100.0)
    assert context.regime_evidence.close_vs_sma20 == Comparison.ABOVE
    assert context.regime_evidence.sma20_vs_sma50 == Comparison.ABOVE


def test_G_missing_sma20_gives_insufficient_data_not_error():
    closes = [100.0]
    market, indicators, dates = _build(closes, [None], [95.0])
    context = build_risk_market_context(market, indicators, dates[0])
    assert context.regime == MarketRegime.INSUFFICIENT_DATA
    assert context.regime_evidence.close_vs_sma20 is None
    assert context.regime_evidence.sma20_vs_sma50 is None


def test_G_missing_sma50_gives_insufficient_data_not_error():
    closes = [100.0]
    market, indicators, dates = _build(closes, [95.0], [None])
    context = build_risk_market_context(market, indicators, dates[0])
    assert context.regime == MarketRegime.INSUFFICIENT_DATA


def test_H_non_finite_sma20_is_rejected_as_invalid_input_not_insufficient_data():
    """A PRESENT-but-malformed value is INVALID INPUT (raises), distinct
    from an ABSENT value (None), which is legitimate INSUFFICIENT_DATA."""
    closes = [100.0]
    market, indicators, dates = _build(closes, [float("nan")], [95.0])
    with pytest.raises(StrategyAuditInputInvalidError):
        build_risk_market_context(market, indicators, dates[0])


def test_non_finite_close_is_invalid_input():
    dates = _dates(1)
    bad_bar = OHLCVBar(date=dates[0], open=100, high=105, low=95, close=float("inf"), adj_close=100, volume=1000)
    market = OHLCVSeries(provider_symbol=SYMBOL, interval=INTERVAL, bars=(bad_bar,))
    indicators = IndicatorSeries(provider_symbol=SYMBOL, interval=INTERVAL, rows=(_row(dates[0], 95.0, 90.0),))
    with pytest.raises(StrategyAuditInputInvalidError):
        build_risk_market_context(market, indicators, dates[0])


# ---------------------------------------------------------------------------
# Look-ahead: A-C
# ---------------------------------------------------------------------------


def test_lookahead_A_mutating_future_prices_does_not_change_result():
    n = 25
    closes_a = [100.0 + i for i in range(n)]
    sma20s = [None] * 19 + [105.0 + i for i in range(n - 19)]
    sma50s = [None] * 19 + [102.0 + i for i in range(n - 19)]
    market_a, indicators_a, dates_a = _build(closes_a, sma20s, sma50s)
    audit_date = dates_a[20]

    closes_b = list(closes_a)
    for j in range(21, n):
        closes_b[j] = 5.0
    market_b, indicators_b, dates_b = _build(closes_b, sma20s, sma50s)
    assert dates_b == dates_a

    context_a = build_risk_market_context(market_a, indicators_a, audit_date)
    context_b = build_risk_market_context(market_b, indicators_b, audit_date)

    assert context_a.regime == context_b.regime
    assert context_a.regime_evidence == context_b.regime_evidence
    assert context_a.annualized_realized_volatility_20 == context_b.annualized_realized_volatility_20


def test_lookahead_B_appending_future_bars_does_not_change_result():
    n = 25
    closes = [100.0 + i for i in range(n)]
    sma20s = [None] * 19 + [105.0 + i for i in range(n - 19)]
    sma50s = [None] * 19 + [102.0 + i for i in range(n - 19)]
    market_short, indicators_short, dates_short = _build(closes, sma20s, sma50s)
    audit_date = dates_short[20]
    context_short = build_risk_market_context(market_short, indicators_short, audit_date)

    extra = 5
    closes_long = closes + [200.0 + j for j in range(extra)]
    sma20s_long = sma20s + [999.0] * extra
    sma50s_long = sma50s + [999.0] * extra
    market_long, indicators_long, dates_long = _build(closes_long, sma20s_long, sma50s_long)
    assert dates_long[: len(closes)] == dates_short
    context_long = build_risk_market_context(market_long, indicators_long, audit_date)

    assert context_short.regime == context_long.regime
    assert context_short.regime_evidence == context_long.regime_evidence
    assert context_short.annualized_realized_volatility_20 == context_long.annualized_realized_volatility_20


def test_lookahead_C_changing_audit_date_close_may_change_result():
    n = 25
    sma20s = [None] * 19 + [105.0 + i for i in range(n - 19)]
    sma50s = [None] * 19 + [102.0 + i for i in range(n - 19)]

    closes_a = [100.0 + i for i in range(n)]
    market_a, indicators_a, dates_a = _build(closes_a, sma20s, sma50s)
    audit_date = dates_a[20]

    closes_b = list(closes_a)
    closes_b[20] = 1.0  # change the AUDIT bar's own close
    market_b, indicators_b, dates_b = _build(closes_b, sma20s, sma50s)

    context_a = build_risk_market_context(market_a, indicators_a, audit_date)
    context_b = build_risk_market_context(market_b, indicators_b, audit_date)

    # This proves the cutoff is audit_date itself (inclusive), not "before
    # audit_date" -- changing the audit bar's own close is allowed to (and
    # here does) change the result.
    assert context_a.regime_evidence.close != context_b.regime_evidence.close


# ---------------------------------------------------------------------------
# Non-mutation / determinism
# ---------------------------------------------------------------------------


def test_deterministic_repeated_execution():
    closes = [100.0 + i for i in range(21)]
    market, indicators, dates = _build(closes, [105.0] * 21, [102.0] * 21)
    audit_date = dates[20]
    a = build_risk_market_context(market, indicators, audit_date)
    b = build_risk_market_context(market, indicators, audit_date)
    assert a == b


def test_no_input_mutation():
    closes = [100.0 + i for i in range(21)]
    market, indicators, dates = _build(closes, [105.0] * 21, [102.0] * 21)
    audit_date = dates[20]
    market_before = copy.deepcopy(market)
    indicators_before = copy.deepcopy(indicators)

    build_risk_market_context(market, indicators, audit_date)

    assert market == market_before
    assert indicators == indicators_before


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_audit_date_not_present_rejected():
    closes = [100.0 + i for i in range(5)]
    market, indicators, dates = _build(closes, [None] * 5, [None] * 5)
    with pytest.raises(StrategyAuditInputInvalidError):
        build_risk_market_context(market, indicators, date(1999, 1, 1))


def test_symbol_mismatch_rejected():
    closes = [100.0 + i for i in range(5)]
    market, indicators, dates = _build(closes, [None] * 5, [None] * 5)
    bad_indicators = IndicatorSeries(provider_symbol="OTHER.NS", interval=INTERVAL, rows=indicators.rows)
    with pytest.raises(StrategyAuditInputInvalidError):
        build_risk_market_context(market, bad_indicators, dates[0])


def test_interval_mismatch_rejected():
    closes = [100.0 + i for i in range(5)]
    market, indicators, dates = _build(closes, [None] * 5, [None] * 5)
    bad_indicators = IndicatorSeries(provider_symbol=SYMBOL, interval="1wk", rows=indicators.rows)
    with pytest.raises(StrategyAuditInputInvalidError):
        build_risk_market_context(market, bad_indicators, dates[0])


def test_row_count_mismatch_rejected():
    closes = [100.0 + i for i in range(5)]
    market, indicators, dates = _build(closes, [None] * 5, [None] * 5)
    bad_indicators = IndicatorSeries(provider_symbol=SYMBOL, interval=INTERVAL, rows=indicators.rows[:-1])
    with pytest.raises(StrategyAuditInputInvalidError):
        build_risk_market_context(market, bad_indicators, dates[0])


def test_date_misalignment_rejected():
    closes = [100.0 + i for i in range(5)]
    market, indicators, dates = _build(closes, [None] * 5, [None] * 5)
    rows = list(indicators.rows)
    rows[2] = _row(rows[2].date + timedelta(days=1), rows[2].sma20, rows[2].sma50)
    bad_indicators = IndicatorSeries(provider_symbol=SYMBOL, interval=INTERVAL, rows=tuple(rows))
    with pytest.raises(StrategyAuditInputInvalidError):
        build_risk_market_context(market, bad_indicators, dates[0])


def test_non_chronological_bars_rejected():
    dates = _dates(4)
    closes = [100.0, 101.0, 102.0, 103.0]
    bars = (
        _bar(dates[0], closes[0]),
        _bar(dates[2], closes[2]),
        _bar(dates[1], closes[1]),
        _bar(dates[3], closes[3]),
    )
    market = OHLCVSeries(provider_symbol=SYMBOL, interval=INTERVAL, bars=bars)
    rows = tuple(_row(b.date, None, None) for b in bars)
    indicators = IndicatorSeries(provider_symbol=SYMBOL, interval=INTERVAL, rows=rows)
    with pytest.raises(StrategyAuditInputInvalidError):
        build_risk_market_context(market, indicators, dates[0])

"""Phase 3C: strategy audit composition engine tests.

Outcomes are generated via the REAL, accepted Phase 2A
`compute_signal_outcomes` (never hand-faked) so MAE/MFE values are
independently hand-verifiable from deliberately engineered bar
low/high windows.
"""

import copy
from datetime import date, timedelta

import pytest

from app.audit.engine import build_strategy_audit
from app.audit.models import MarketRegime
from app.core.exceptions import StrategyAuditInputInvalidError
from app.indicators.models import IndicatorRow, IndicatorSeries
from app.market_data.models import OHLCVBar, OHLCVSeries
from app.outcomes.engine import compute_signal_outcomes
from app.strategies.models import StrategyDecision, StrategyEvaluation, StrategyEvaluationSeries

SYMBOL = "X.NS"
INTERVAL = "1d"
STRATEGY_ID = "trend_momentum_v1"
STRATEGY_NAME = "Trend + Momentum v1"

_GAPS = [1, 1, 3, 1, 3, 1, 1, 3, 1, 3, 1, 1, 3, 1, 3, 1, 1, 3, 1, 3, 1, 1]


def _dates(n: int, start: date = date(2024, 1, 1)) -> list[date]:
    dates = [start]
    for i in range(n - 1):
        dates.append(dates[-1] + timedelta(days=_GAPS[i % len(_GAPS)]))
    return dates


def _bar(d: date, close: float, low: float | None = None, high: float | None = None) -> OHLCVBar:
    low = close - 5 if low is None else low
    high = close + 5 if high is None else high
    return OHLCVBar(date=d, open=close, high=high, low=low, close=close, adj_close=close, volume=1000)


def _evaluation(d: date, decision: StrategyDecision) -> StrategyEvaluation:
    return StrategyEvaluation(
        date=d, strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME, decision=decision, conditions=(), missing_inputs=()
    )


def _row(d: date, sma20: float | None = None, sma50: float | None = None) -> IndicatorRow:
    return IndicatorRow(date=d, sma20=sma20, sma50=sma50, rsi14=None, average_volume=None, volume_ratio=None)


def _finish(bars, decisions, sma20s=None, sma50s=None, symbol=SYMBOL, interval=INTERVAL):
    market = OHLCVSeries(provider_symbol=symbol, interval=interval, bars=tuple(bars))
    dates = [b.date for b in bars]
    evals = tuple(_evaluation(d, dec) for d, dec in zip(dates, decisions))
    evaluations = StrategyEvaluationSeries(
        provider_symbol=symbol, interval=interval, strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME, evaluations=evals
    )
    outcomes = compute_signal_outcomes(market, evaluations)
    sma20s = sma20s or [None] * len(bars)
    sma50s = sma50s or [None] * len(bars)
    rows = tuple(_row(d, s20, s50) for d, s20, s50 in zip(dates, sma20s, sma50s))
    indicators = IndicatorSeries(provider_symbol=symbol, interval=interval, rows=rows)
    return market, evaluations, outcomes, indicators, dates


# ---------------------------------------------------------------------------
# Hand-derived HistoricalSignalRisk reference fixture (section 10)
# ---------------------------------------------------------------------------


def _historical_signal_risk_fixture(audit_index: int = 45, n: int = 46, extra_buy_indices: set[int] | None = None):
    """Three prior BUY signals, each with an isolated, non-overlapping
    10-bar MAE/MFE window engineered to hand-verifiable exact values:

      signal @ index 0:  window bars[1..10]  -> low=98,  high=104 (ref=100)
                          -> mae=-0.02, mfe=+0.04
      signal @ index 15: window bars[16..25] -> low=95,  high=108 (ref=100)
                          -> mae=-0.05, mfe=+0.08
      signal @ index 30: window bars[31..40] -> low=99,  high=103 (ref=100)
                          -> mae=-0.01, mfe=+0.03

    All three are 10-bar-eligible as of audit_index=45 (0+10, 15+10,
    30+10 all <= 45).
    """
    bars = []
    for i in range(n):
        if 1 <= i <= 10:
            bars.append(_bar(_dates(n)[i], 100.0, low=98.0, high=104.0))
        elif 16 <= i <= 25:
            bars.append(_bar(_dates(n)[i], 100.0, low=95.0, high=108.0))
        elif 31 <= i <= 40:
            bars.append(_bar(_dates(n)[i], 100.0, low=99.0, high=103.0))
        else:
            bars.append(_bar(_dates(n)[i], 100.0, low=95.0, high=105.0))
    dates = _dates(n)
    bars = [
        OHLCVBar(date=d, open=b.open, high=b.high, low=b.low, close=b.close, adj_close=b.adj_close, volume=b.volume)
        for d, b in zip(dates, bars)
    ]
    buy_indices = {0, 15, 30} | (extra_buy_indices or set())
    decisions = [StrategyDecision.BUY if i in buy_indices else StrategyDecision.NO_SIGNAL for i in range(n)]
    return _finish(bars, decisions)


def test_hand_derived_historical_signal_risk_exact_arithmetic():
    market, evaluations, outcomes, indicators, dates = _historical_signal_risk_fixture()
    audit_date = dates[45]

    audit = build_strategy_audit(market, evaluations, outcomes, indicators, audit_date)
    risk = audit.historical_signal_risk

    assert risk.eligible_outcome_count == 3
    assert risk.average_mae_10d == pytest.approx((-0.02 - 0.05 - 0.01) / 3)
    assert risk.worst_mae_10d == pytest.approx(-0.05)
    assert risk.average_mfe_10d == pytest.approx((0.04 + 0.08 + 0.03) / 3)
    assert risk.best_mfe_10d == pytest.approx(0.08)

    # Signed decimal fractions preserved verbatim -- never abs()'d.
    assert risk.worst_mae_10d < 0
    assert risk.best_mfe_10d > 0


def test_cross_check_3a_3c_population_invariant():
    market, evaluations, outcomes, indicators, dates = _historical_signal_risk_fixture()
    audit_date = dates[45]
    audit = build_strategy_audit(market, evaluations, outcomes, indicators, audit_date)
    assert audit.historical_signal_risk.eligible_outcome_count == audit.historical_evidence.ten_bar.eligible_outcome_count


def test_zero_eligible_outcomes():
    n = 10
    dates = _dates(n)
    bars = [_bar(d, 100.0 + i) for i, d in enumerate(dates)]
    decisions = [StrategyDecision.NO_SIGNAL] * n
    market, evaluations, outcomes, indicators, dates = _finish(bars, decisions)
    audit_date = dates[9]

    audit = build_strategy_audit(market, evaluations, outcomes, indicators, audit_date)
    risk = audit.historical_signal_risk
    assert risk.eligible_outcome_count == 0
    assert risk.average_mae_10d is None
    assert risk.worst_mae_10d is None
    assert risk.average_mfe_10d is None
    assert risk.best_mfe_10d is None


# ---------------------------------------------------------------------------
# D/E/F/G: audit-date/post-audit exclusion + exact horizon boundary
# ---------------------------------------------------------------------------


def test_D_audit_date_buy_never_enters_historical_signal_risk():
    market, evaluations, outcomes, indicators, dates = _historical_signal_risk_fixture()
    # Re-run with the audit bar itself also a BUY -- must not add a 4th
    # eligible observation (it has no completed 10-bar window from its own
    # perspective as a "prior" signal; it's excluded structurally).
    bars = list(market.bars)
    decisions = [
        StrategyDecision.BUY if b.date in (dates[0], dates[15], dates[30], dates[45]) else StrategyDecision.NO_SIGNAL
        for b in bars
    ]
    market2, evaluations2, outcomes2, indicators2, dates2 = _finish(bars, decisions)
    audit_date = dates2[45]

    audit = build_strategy_audit(market2, evaluations2, outcomes2, indicators2, audit_date)
    assert audit.historical_signal_risk.eligible_outcome_count == 3  # not 4
    assert audit.evaluation.decision == StrategyDecision.BUY  # confirms audit bar really is BUY


def test_E_post_audit_buy_never_enters_historical_signal_risk():
    market, evaluations, outcomes, indicators, dates = _historical_signal_risk_fixture(n=46)
    # Extend with one more bar after the original audit_index=45 that is BUY.
    bars = list(market.bars)
    extra_date = dates[-1] + timedelta(days=1)
    bars.append(_bar(extra_date, 100.0))
    decisions = [
        StrategyDecision.BUY if b.date in (dates[0], dates[15], dates[30]) else StrategyDecision.NO_SIGNAL
        for b in bars[:-1]
    ] + [StrategyDecision.BUY]  # the appended post-audit bar is BUY
    market2, evaluations2, outcomes2, indicators2, dates2 = _finish(bars, decisions)
    audit_date = dates2[45]  # unchanged, still the original audit bar

    audit = build_strategy_audit(market2, evaluations2, outcomes2, indicators2, audit_date)
    assert audit.historical_signal_risk.eligible_outcome_count == 3  # the post-audit BUY never counts


def test_F_10th_bar_exactly_on_audit_date_is_eligible():
    # Signal at index 30, audit at index 40 -> 30+10=40 == audit_index (boundary, inclusive).
    market, evaluations, outcomes, indicators, dates = _historical_signal_risk_fixture()
    audit_date = dates[40]
    audit = build_strategy_audit(market, evaluations, outcomes, indicators, audit_date)
    # Signals @0 (0+10=10<=40) and @15 (15+10=25<=40) and @30 (30+10=40<=40) all eligible.
    assert audit.historical_signal_risk.eligible_outcome_count == 3


def test_G_10th_bar_after_audit_date_is_not_eligible():
    # Signal at index 30 needs bar 40; audit at index 39 -> 40 > 39, excluded.
    market, evaluations, outcomes, indicators, dates = _historical_signal_risk_fixture()
    audit_date = dates[39]
    audit = build_strategy_audit(market, evaluations, outcomes, indicators, audit_date)
    # Only @0 and @15 remain eligible (@30 needs bar 40, not yet knowable at 39).
    assert audit.historical_signal_risk.eligible_outcome_count == 2


# ---------------------------------------------------------------------------
# A/B/C: strict no-look-ahead across the FULL composed StrategyAudit
# ---------------------------------------------------------------------------


def test_A_future_price_mutation_isolated_from_all_point_in_time_sections():
    market, evaluations, outcomes, indicators, dates = _historical_signal_risk_fixture()
    audit_date = dates[45]
    audit_a = build_strategy_audit(market, evaluations, outcomes, indicators, audit_date)

    # The fixture ends exactly at audit_index (45), so there are no bars
    # strictly after it to mutate in place -- extend first, then mutate
    # only the extension (still strictly after audit_date).
    bars_b = list(market.bars)
    extra_dates = [dates[-1] + timedelta(days=k) for k in (1, 2, 3)]
    bars_b = bars_b + [_bar(d, 9999.0, low=1.0, high=99999.0) for d in extra_dates]
    decisions_b = [
        StrategyDecision.BUY if b.date in (dates[0], dates[15], dates[30]) else StrategyDecision.NO_SIGNAL
        for b in bars_b
    ]
    market_b, evaluations_b, outcomes_b, indicators_b, dates_b = _finish(bars_b, decisions_b)

    audit_b = build_strategy_audit(market_b, evaluations_b, outcomes_b, indicators_b, audit_date)

    assert audit_a.evaluation == audit_b.evaluation
    assert audit_a.historical_evidence == audit_b.historical_evidence
    assert audit_a.historical_signal_risk == audit_b.historical_signal_risk
    assert audit_a.risk_market_context == audit_b.risk_market_context


def test_B_retrospective_outcome_may_change_after_future_price_mutation():
    n = 12
    dates = _dates(n)
    bars = [_bar(d, 100.0 + i) for i, d in enumerate(dates)]
    decisions = [StrategyDecision.BUY if i == 1 else StrategyDecision.NO_SIGNAL for i in range(n)]
    market_a, evaluations_a, outcomes_a, indicators_a, dates_a = _finish(bars, decisions)
    audit_date = dates_a[1]

    bars_b = list(bars)
    for j in range(2, n):
        bars_b[j] = _bar(dates[j], 500.0)
    market_b, evaluations_b, outcomes_b, indicators_b, dates_b = _finish(bars_b, decisions)

    audit_a = build_strategy_audit(market_a, evaluations_a, outcomes_a, indicators_a, audit_date)
    audit_b = build_strategy_audit(market_b, evaluations_b, outcomes_b, indicators_b, audit_date)

    assert audit_a.retrospective_outcome != audit_b.retrospective_outcome
    # But point-in-time sections remain identical.
    assert audit_a.historical_evidence == audit_b.historical_evidence
    assert audit_a.historical_signal_risk == audit_b.historical_signal_risk


def test_C_appending_future_bars_does_not_change_point_in_time_sections():
    market, evaluations, outcomes, indicators, dates = _historical_signal_risk_fixture()
    audit_date = dates[45]
    audit_short = build_strategy_audit(market, evaluations, outcomes, indicators, audit_date)

    extra_dates = [dates[-1] + timedelta(days=k) for k in (1, 2, 3, 4, 5)]
    bars_long = list(market.bars) + [_bar(d, 100.0 + k) for k, d in enumerate(extra_dates)]
    decisions_long = [
        StrategyDecision.BUY if b.date in (dates[0], dates[15], dates[30]) else StrategyDecision.NO_SIGNAL
        for b in bars_long
    ]
    market_long, evaluations_long, outcomes_long, indicators_long, dates_long = _finish(bars_long, decisions_long)

    audit_long = build_strategy_audit(market_long, evaluations_long, outcomes_long, indicators_long, audit_date)

    assert audit_short.evaluation == audit_long.evaluation
    assert audit_short.historical_evidence == audit_long.historical_evidence
    assert audit_short.historical_signal_risk == audit_long.historical_signal_risk
    assert audit_short.risk_market_context == audit_long.risk_market_context


# ---------------------------------------------------------------------------
# BUY / NO_SIGNAL / INSUFFICIENT_DATA audit-date variants
# ---------------------------------------------------------------------------


def test_buy_audit_date_full_composition():
    n = 12
    dates = _dates(n)
    bars = [_bar(d, 100.0 + i) for i, d in enumerate(dates)]
    decisions = [StrategyDecision.BUY if i in (1, 8) else StrategyDecision.NO_SIGNAL for i in range(n)]
    market, evaluations, outcomes, indicators, dates = _finish(bars, decisions)
    audit_date = dates[8]  # BUY, with one prior BUY at index 1

    audit = build_strategy_audit(market, evaluations, outcomes, indicators, audit_date)

    assert audit.evaluation.decision == StrategyDecision.BUY
    assert audit.historical_evidence.prior_signal_count == 1
    assert audit.retrospective_outcome is not None
    assert audit.retrospective_outcome.decision == StrategyDecision.BUY


def test_no_signal_audit_date_retrospective_none_but_priors_exist():
    n = 12
    dates = _dates(n)
    bars = [_bar(d, 100.0 + i) for i, d in enumerate(dates)]
    decisions = [StrategyDecision.BUY if i == 1 else StrategyDecision.NO_SIGNAL for i in range(n)]
    market, evaluations, outcomes, indicators, dates = _finish(bars, decisions)
    audit_date = dates[11]  # NO_SIGNAL

    audit = build_strategy_audit(market, evaluations, outcomes, indicators, audit_date)

    assert audit.evaluation.decision == StrategyDecision.NO_SIGNAL
    assert audit.retrospective_outcome is None
    assert audit.historical_evidence.prior_signal_count == 1  # prior BUY evidence still exists


def test_insufficient_data_audit_date():
    n = 5
    dates = _dates(n)
    bars = [_bar(d, 100.0 + i) for i, d in enumerate(dates)]
    decisions = [StrategyDecision.INSUFFICIENT_DATA if i == 0 else StrategyDecision.NO_SIGNAL for i in range(n)]
    market, evaluations, outcomes, indicators, dates = _finish(bars, decisions)
    audit_date = dates[0]

    audit = build_strategy_audit(market, evaluations, outcomes, indicators, audit_date)

    assert audit.evaluation.decision == StrategyDecision.INSUFFICIENT_DATA
    assert audit.retrospective_outcome is None
    assert audit.historical_evidence.prior_signal_count == 0
    # Regime/volatility are independently determined by market/indicator
    # data, not by the strategy decision -- may be INSUFFICIENT_DATA or
    # valid, but must not error out.
    assert audit.risk_market_context.regime in MarketRegime


# ---------------------------------------------------------------------------
# Determinism / non-mutation
# ---------------------------------------------------------------------------


def test_deterministic_repeated_execution():
    market, evaluations, outcomes, indicators, dates = _historical_signal_risk_fixture()
    audit_date = dates[45]
    a = build_strategy_audit(market, evaluations, outcomes, indicators, audit_date)
    b = build_strategy_audit(market, evaluations, outcomes, indicators, audit_date)
    assert a == b


def test_no_input_mutation():
    market, evaluations, outcomes, indicators, dates = _historical_signal_risk_fixture()
    audit_date = dates[45]
    market_before = copy.deepcopy(market)
    evaluations_before = copy.deepcopy(evaluations)
    outcomes_before = copy.deepcopy(outcomes)
    indicators_before = copy.deepcopy(indicators)

    build_strategy_audit(market, evaluations, outcomes, indicators, audit_date)

    assert market == market_before
    assert evaluations == evaluations_before
    assert outcomes == outcomes_before
    assert indicators == indicators_before


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_audit_date_not_present_rejected():
    market, evaluations, outcomes, indicators, dates = _historical_signal_risk_fixture()
    with pytest.raises(StrategyAuditInputInvalidError):
        build_strategy_audit(market, evaluations, outcomes, indicators, date(1999, 1, 1))


def test_indicator_symbol_mismatch_rejected():
    market, evaluations, outcomes, indicators, dates = _historical_signal_risk_fixture()
    bad_indicators = IndicatorSeries(provider_symbol="OTHER.NS", interval=INTERVAL, rows=indicators.rows)
    with pytest.raises(StrategyAuditInputInvalidError):
        build_strategy_audit(market, evaluations, outcomes, bad_indicators, dates[45])


def test_evaluation_symbol_mismatch_rejected():
    market, evaluations, outcomes, indicators, dates = _historical_signal_risk_fixture()
    bad_evaluations = StrategyEvaluationSeries(
        provider_symbol="OTHER.NS", interval=INTERVAL, strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME,
        evaluations=evaluations.evaluations,
    )
    with pytest.raises(StrategyAuditInputInvalidError):
        build_strategy_audit(market, bad_evaluations, outcomes, indicators, dates[45])


def test_missing_mae_mfe_on_eligible_outcome_rejected():
    market, evaluations, outcomes, indicators, dates = _historical_signal_risk_fixture()
    # Corrupt one of the 10-bar-eligible outcomes to lack mae/mfe.
    bad_outcomes_list = []
    for o in outcomes.outcomes:
        if o.date == dates[0]:
            bad_outcomes_list.append(
                type(o)(
                    date=o.date, decision=o.decision, reference_close=o.reference_close,
                    forward_close_5d=o.forward_close_5d, forward_return_5d=o.forward_return_5d,
                    forward_close_10d=o.forward_close_10d, forward_return_10d=o.forward_return_10d,
                    mae_10d=None, mfe_10d=None, available_forward_bars=o.available_forward_bars,
                )
            )
        else:
            bad_outcomes_list.append(o)
    bad_outcomes = type(outcomes)(
        provider_symbol=outcomes.provider_symbol, interval=outcomes.interval, strategy_id=outcomes.strategy_id,
        strategy_name=outcomes.strategy_name, outcomes=tuple(bad_outcomes_list),
    )
    with pytest.raises(StrategyAuditInputInvalidError):
        build_strategy_audit(market, evaluations, bad_outcomes, indicators, dates[45])

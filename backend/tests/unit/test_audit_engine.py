"""Phase 3A: point-in-time strategy audit evidence engine tests.

Outcome series are generated via the REAL, accepted Phase 2A
`compute_signal_outcomes` (never hand-faked) so fixtures stay structurally
self-consistent and forward returns are independently hand-verifiable from
a simple `close[i] = 100 + i` linear series.
"""

import copy
from datetime import date, timedelta

import pytest

from app.audit.engine import build_strategy_audit_evidence
from app.core.exceptions import StrategyAuditInputInvalidError
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


def _bar(d: date, close: float) -> OHLCVBar:
    return OHLCVBar(date=d, open=close, high=close + 5, low=close - 5, close=close, adj_close=close, volume=1000)


def _evaluation(d: date, decision: StrategyDecision) -> StrategyEvaluation:
    return StrategyEvaluation(
        date=d, strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME, decision=decision, conditions=(), missing_inputs=()
    )


def _build(closes: list[float], buy_indices: set[int], symbol: str = SYMBOL, interval: str = INTERVAL):
    dates = _dates(len(closes))
    bars = tuple(_bar(d, c) for d, c in zip(dates, closes))
    market = OHLCVSeries(provider_symbol=symbol, interval=interval, bars=bars)
    evals = tuple(
        _evaluation(d, StrategyDecision.BUY if i in buy_indices else StrategyDecision.NO_SIGNAL)
        for i, d in enumerate(dates)
    )
    evaluations = StrategyEvaluationSeries(
        provider_symbol=symbol, interval=interval, strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME, evaluations=evals
    )
    outcomes = compute_signal_outcomes(market, evaluations)
    return market, evaluations, outcomes, dates


# ---------------------------------------------------------------------------
# Hand-derived reference fixture (section 12): fully-eligible / 5D-only /
# too-recent prior signals + a BUY audit signal + a signal after audit_date.
# ---------------------------------------------------------------------------


def _reference_fixture():
    """n=20, close[i] = 100+i. BUY at indices 2, 8, 13, 17, 18 (audit), 19
    (after audit -- must never count). audit_date = index 18.

    Eligibility at audit_index=18:
      i=2:  i+5=7<=18 (5D eligible), i+10=12<=18 (10D eligible) -- both.
      i=8:  i+5=13<=18 (5D eligible), i+10=18<=18 (10D eligible, EXACT
            boundary -- included).
      i=13: i+5=18<=18 (5D eligible, EXACT boundary -- included),
            i+10=23>18 (10D NOT eligible).
      i=17: i+5=22>18, i+10=27>18 -- too recent for either.
      i=19: after audit_date -- excluded entirely, never counted.
    """
    closes = [100.0 + i for i in range(20)]
    buy_indices = {2, 8, 13, 17, 18, 19}
    market, evaluations, outcomes, dates = _build(closes, buy_indices)
    audit_date = dates[18]
    return market, evaluations, outcomes, dates, audit_date


def test_reference_fixture_hand_derived_counts_and_arithmetic():
    market, evaluations, outcomes, dates, audit_date = _reference_fixture()

    evidence = build_strategy_audit_evidence(market, evaluations, outcomes, audit_date)

    # prior_signal_count: ALL prior BUY (2, 8, 13, 17) -- NOT 18 (the audit
    # signal itself) and NOT 19 (after audit_date).
    assert evidence.historical_evidence.prior_signal_count == 4

    five = evidence.historical_evidence.five_bar
    ten = evidence.historical_evidence.ten_bar

    # 5D eligible: i=2, 8, 13 (three). 10D eligible: i=2, 8 (two).
    assert five.eligible_outcome_count == 3
    assert ten.eligible_outcome_count == 2
    assert evidence.historical_evidence.prior_signal_count >= five.eligible_outcome_count >= ten.eligible_outcome_count

    # Hand-derived exact returns: forward_return_h = close[i+h]/close[i] - 1.
    r5_2 = 107.0 / 102.0 - 1
    r5_8 = 113.0 / 108.0 - 1
    r5_13 = 118.0 / 113.0 - 1
    r10_2 = 112.0 / 102.0 - 1
    r10_8 = 118.0 / 108.0 - 1

    assert five.positive_count == 3
    assert five.negative_count == 0
    assert five.breakeven_count == 0
    assert five.hit_rate == pytest.approx(1.0)
    assert five.average_return == pytest.approx((r5_2 + r5_8 + r5_13) / 3)

    assert ten.positive_count == 2
    assert ten.hit_rate == pytest.approx(1.0)
    assert ten.average_return == pytest.approx((r10_2 + r10_8) / 2)

    # Retrospective outcome for the audit-date BUY (index 18, close=118):
    # near series end (only 1 future bar), so +5D/+10D/MAE/MFE censored.
    retro = evidence.retrospective_outcome
    assert retro is not None
    assert retro.reference_close == pytest.approx(118.0)
    assert retro.forward_close_5d is None
    assert retro.forward_return_5d is None
    assert retro.forward_close_10d is None
    assert retro.mae_10d is None
    assert retro.mfe_10d is None
    assert retro.available_forward_bars == 1

    assert evidence.evaluation.decision == StrategyDecision.BUY
    assert evidence.evaluation.date == audit_date
    assert evidence.audit_date == audit_date


# ---------------------------------------------------------------------------
# A/B: audit signal and post-audit signals excluded from prior population
# ---------------------------------------------------------------------------


def test_audit_date_signal_excluded_from_prior_statistics():
    market, evaluations, outcomes, dates, audit_date = _reference_fixture()
    evidence = build_strategy_audit_evidence(market, evaluations, outcomes, audit_date)
    # 4, not 5 -- the audit signal at index 18 must not count itself.
    assert evidence.historical_evidence.prior_signal_count == 4


def test_signals_after_audit_date_excluded():
    market, evaluations, outcomes, dates, audit_date = _reference_fixture()
    evidence = build_strategy_audit_evidence(market, evaluations, outcomes, audit_date)
    # Index 19 (after audit_date) is BUY in the fixture but must never be
    # counted -- prior_signal_count stays 4, not 5.
    assert evidence.historical_evidence.prior_signal_count == 4


# ---------------------------------------------------------------------------
# C/D/E: exact eligibility boundary (knowable ON audit_date is included;
# only-knowable-after is excluded)
# ---------------------------------------------------------------------------


def test_5d_outcome_known_after_audit_date_is_excluded():
    """A prior signal whose +5D horizon completes AFTER audit_date (i=17,
    needs bar 22, audit is at 18) must be excluded from the 5D population."""
    market, evaluations, outcomes, dates, audit_date = _reference_fixture()
    evidence = build_strategy_audit_evidence(market, evaluations, outcomes, audit_date)
    assert evidence.historical_evidence.five_bar.eligible_outcome_count == 3  # not 4


def test_5d_outcome_completing_exactly_on_audit_date_is_included():
    """i=13: i+5 == 18 == audit_index -- included (boundary is inclusive)."""
    market, evaluations, outcomes, dates, audit_date = _reference_fixture()
    evidence = build_strategy_audit_evidence(market, evaluations, outcomes, audit_date)
    r5_13 = 118.0 / 113.0 - 1
    # Confirm i=13's return is actually present in the 3-signal average by
    # checking the average matches (see full arithmetic test above); here
    # just assert the count includes it.
    assert evidence.historical_evidence.five_bar.eligible_outcome_count == 3
    assert r5_13 > 0  # sanity: it's a real, meaningful contribution


def test_10d_outcome_completing_exactly_on_audit_date_is_included():
    """i=8: i+10 == 18 == audit_index -- included (boundary is inclusive)."""
    market, evaluations, outcomes, dates, audit_date = _reference_fixture()
    evidence = build_strategy_audit_evidence(market, evaluations, outcomes, audit_date)
    assert evidence.historical_evidence.ten_bar.eligible_outcome_count == 2  # includes i=8


def test_10d_outcome_known_after_audit_date_is_excluded():
    """i=13: i+10 = 23 > 18 -- excluded from the 10D population."""
    market, evaluations, outcomes, dates, audit_date = _reference_fixture()
    evidence = build_strategy_audit_evidence(market, evaluations, outcomes, audit_date)
    assert evidence.historical_evidence.ten_bar.eligible_outcome_count == 2  # not 3


# ---------------------------------------------------------------------------
# F/G: strict no-look-ahead -- future bars cannot change point-in-time
# historical evidence, only the audit signal's own retrospective outcome
# ---------------------------------------------------------------------------


def test_prices_after_audit_date_never_change_historical_evidence():
    closes_a = [100.0 + i for i in range(20)]
    buy_indices = {2, 8, 13, 17, 18}
    market_a, evaluations_a, outcomes_a, dates_a = _build(closes_a, buy_indices)
    audit_date = dates_a[18]

    # Variant B: identical through audit_date, wildly different after.
    closes_b = list(closes_a)
    closes_b[19] = 99999.0
    market_b, evaluations_b, outcomes_b, dates_b = _build(closes_b, buy_indices)
    assert dates_b == dates_a  # same calendar layout, only price at 19 differs

    evidence_a = build_strategy_audit_evidence(market_a, evaluations_a, outcomes_a, audit_date)
    evidence_b = build_strategy_audit_evidence(market_b, evaluations_b, outcomes_b, audit_date)

    assert evidence_a.historical_evidence == evidence_b.historical_evidence


def test_extending_series_beyond_audit_date_only_de_censors_retrospective_outcome():
    """Adding MORE future bars after audit_date must not alter
    prior_signal_count/5D/10D historical evidence -- only the audit
    signal's own retrospective outcome may become less censored."""
    closes_short = [100.0 + i for i in range(19)]  # audit is the final bar (index 18)
    buy_indices = {2, 8, 13, 17, 18}
    market_short, evaluations_short, outcomes_short, dates_short = _build(closes_short, buy_indices)
    audit_date = dates_short[18]

    evidence_short = build_strategy_audit_evidence(market_short, evaluations_short, outcomes_short, audit_date)
    # Series ends AT the audit bar -- fully censored retrospective outcome.
    assert evidence_short.retrospective_outcome.forward_close_5d is None
    assert evidence_short.retrospective_outcome.available_forward_bars == 0

    # Extend with 10 more bars beyond audit_date (dates continue chronologically).
    closes_long = closes_short + [118.0 + j for j in range(1, 11)]
    market_long, evaluations_long, outcomes_long, dates_long = _build(closes_long, buy_indices)
    assert dates_long[:19] == dates_short  # unchanged calendar layout up to and incl. audit bar

    evidence_long = build_strategy_audit_evidence(market_long, evaluations_long, outcomes_long, audit_date)

    # Point-in-time historical evidence is byte-identical.
    assert evidence_long.historical_evidence == evidence_short.historical_evidence
    # But the retrospective outcome is now LESS censored (hindsight).
    assert evidence_long.retrospective_outcome.forward_close_5d is not None
    assert evidence_long.retrospective_outcome.forward_return_5d is not None


# ---------------------------------------------------------------------------
# Classification / hit-rate / breakeven fixture
# ---------------------------------------------------------------------------


def _classification_fixture():
    """n=10. Three prior BUY signals at i=0,1,2, each 5D-eligible as of
    audit_date (index 9). Closes engineered for exact +10%/-10%/0% returns.
    No 10D-eligible signal exists (i+10<=9 is impossible for i>=0)."""
    closes = [100.0] * 10
    closes[0], closes[5] = 100.0, 110.0  # signal i=0 -> +10%
    closes[1], closes[6] = 100.0, 90.0  # signal i=1 -> -10%
    closes[2], closes[7] = 100.0, 100.0  # signal i=2 -> 0% (breakeven)
    market, evaluations, outcomes, dates = _build(closes, buy_indices={0, 1, 2})
    audit_date = dates[9]
    return market, evaluations, outcomes, dates, audit_date


def test_classification_positive_negative_breakeven_and_hit_rate():
    market, evaluations, outcomes, dates, audit_date = _classification_fixture()
    evidence = build_strategy_audit_evidence(market, evaluations, outcomes, audit_date)

    five = evidence.historical_evidence.five_bar
    assert five.eligible_outcome_count == 3
    assert five.positive_count == 1
    assert five.negative_count == 1
    assert five.breakeven_count == 1  # stays in the denominator
    assert five.hit_rate == pytest.approx(1 / 3)
    assert five.average_return == pytest.approx((0.10 - 0.10 + 0.0) / 3)
    assert five.average_return == pytest.approx(0.0, abs=1e-12)


def test_prior_signals_exist_but_zero_eligible_for_10d():
    market, evaluations, outcomes, dates, audit_date = _classification_fixture()
    evidence = build_strategy_audit_evidence(market, evaluations, outcomes, audit_date)

    assert evidence.historical_evidence.prior_signal_count == 3
    ten = evidence.historical_evidence.ten_bar
    assert ten.eligible_outcome_count == 0
    assert ten.positive_count == 0
    assert ten.negative_count == 0
    assert ten.breakeven_count == 0
    assert ten.hit_rate is None
    assert ten.average_return is None


def test_zero_prior_signals():
    closes = [100.0 + i for i in range(10)]
    market, evaluations, outcomes, dates = _build(closes, buy_indices=set())
    audit_date = dates[9]
    evaluations = StrategyEvaluationSeries(
        provider_symbol=SYMBOL, interval=INTERVAL, strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME,
        evaluations=tuple(_evaluation(d, StrategyDecision.NO_SIGNAL) for d in dates),
    )
    outcomes = compute_signal_outcomes(market, evaluations)

    evidence = build_strategy_audit_evidence(market, evaluations, outcomes, audit_date)

    assert evidence.historical_evidence.prior_signal_count == 0
    assert evidence.historical_evidence.five_bar.eligible_outcome_count == 0
    assert evidence.historical_evidence.five_bar.hit_rate is None
    assert evidence.historical_evidence.ten_bar.eligible_outcome_count == 0


# ---------------------------------------------------------------------------
# Audit decision variants: BUY / NO_SIGNAL / INSUFFICIENT_DATA
# ---------------------------------------------------------------------------


def test_audit_no_signal_has_no_retrospective_outcome():
    closes = [100.0 + i for i in range(10)]
    dates = _dates(len(closes))
    bars = tuple(_bar(d, c) for d, c in zip(dates, closes))
    market = OHLCVSeries(provider_symbol=SYMBOL, interval=INTERVAL, bars=bars)
    evals = tuple(
        _evaluation(d, StrategyDecision.BUY if i == 2 else StrategyDecision.NO_SIGNAL) for i, d in enumerate(dates)
    )
    evaluations = StrategyEvaluationSeries(
        provider_symbol=SYMBOL, interval=INTERVAL, strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME, evaluations=evals
    )
    outcomes = compute_signal_outcomes(market, evaluations)
    audit_date = dates[9]  # NO_SIGNAL

    evidence = build_strategy_audit_evidence(market, evaluations, outcomes, audit_date)

    assert evidence.evaluation.decision == StrategyDecision.NO_SIGNAL
    assert evidence.retrospective_outcome is None
    assert evidence.historical_evidence.prior_signal_count == 1  # the BUY at index 2 still counts


def test_audit_insufficient_data_has_no_retrospective_outcome():
    closes = [100.0 + i for i in range(10)]
    dates = _dates(len(closes))
    bars = tuple(_bar(d, c) for d, c in zip(dates, closes))
    market = OHLCVSeries(provider_symbol=SYMBOL, interval=INTERVAL, bars=bars)
    evals = tuple(
        _evaluation(d, StrategyDecision.INSUFFICIENT_DATA if i == 0 else StrategyDecision.NO_SIGNAL)
        for i, d in enumerate(dates)
    )
    evaluations = StrategyEvaluationSeries(
        provider_symbol=SYMBOL, interval=INTERVAL, strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME, evaluations=evals
    )
    outcomes = compute_signal_outcomes(market, evaluations)
    audit_date = dates[0]

    evidence = build_strategy_audit_evidence(market, evaluations, outcomes, audit_date)

    assert evidence.evaluation.decision == StrategyDecision.INSUFFICIENT_DATA
    assert evidence.retrospective_outcome is None
    assert evidence.historical_evidence.prior_signal_count == 0  # index 0 has no priors at all


def test_censored_retrospective_buy_outcome_preserved_as_none():
    market, evaluations, outcomes, dates, audit_date = _reference_fixture()
    evidence = build_strategy_audit_evidence(market, evaluations, outcomes, audit_date)
    # Reference fixture's audit signal (index 18 of 20) is near the end --
    # its 5D/10D retrospective fields are censored (None), never fabricated.
    assert evidence.retrospective_outcome.forward_return_5d is None
    assert evidence.retrospective_outcome.forward_return_10d is None


# ---------------------------------------------------------------------------
# Determinism / non-mutation
# ---------------------------------------------------------------------------


def test_deterministic_repeated_execution():
    market, evaluations, outcomes, dates, audit_date = _reference_fixture()
    a = build_strategy_audit_evidence(market, evaluations, outcomes, audit_date)
    b = build_strategy_audit_evidence(market, evaluations, outcomes, audit_date)
    assert a == b


def test_no_input_mutation():
    market, evaluations, outcomes, dates, audit_date = _reference_fixture()
    market_before = copy.deepcopy(market)
    evaluations_before = copy.deepcopy(evaluations)
    outcomes_before = copy.deepcopy(outcomes)

    build_strategy_audit_evidence(market, evaluations, outcomes, audit_date)

    assert market == market_before
    assert evaluations == evaluations_before
    assert outcomes == outcomes_before


# ---------------------------------------------------------------------------
# Validation: alignment, audit date presence, malformed input
# ---------------------------------------------------------------------------


def test_audit_date_not_present_rejected():
    market, evaluations, outcomes, dates, _ = _reference_fixture()
    with pytest.raises(StrategyAuditInputInvalidError):
        build_strategy_audit_evidence(market, evaluations, outcomes, date(1999, 1, 1))


def test_audit_date_not_silently_reinterpreted_to_nearest_bar():
    """A date near (but not equal to) a real bar date must be rejected
    outright, never silently snapped to the nearest trading day."""
    market, evaluations, outcomes, dates, audit_date = _reference_fixture()
    near_miss = next(
        candidate
        for offset in range(1, 5)
        for candidate in (audit_date + timedelta(days=offset), audit_date - timedelta(days=offset))
        if candidate not in dates
    )
    with pytest.raises(StrategyAuditInputInvalidError):
        build_strategy_audit_evidence(market, evaluations, outcomes, near_miss)


def test_symbol_mismatch_rejected():
    market, evaluations, outcomes, dates, audit_date = _reference_fixture()
    bad_outcomes = compute_signal_outcomes(
        OHLCVSeries(provider_symbol="OTHER.NS", interval=INTERVAL, bars=market.bars),
        StrategyEvaluationSeries(
            provider_symbol="OTHER.NS", interval=INTERVAL, strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME,
            evaluations=evaluations.evaluations,
        ),
    )
    with pytest.raises(StrategyAuditInputInvalidError):
        build_strategy_audit_evidence(market, evaluations, bad_outcomes, audit_date)


def test_interval_mismatch_rejected():
    market, evaluations, outcomes, dates, audit_date = _reference_fixture()
    bad_evaluations = StrategyEvaluationSeries(
        provider_symbol=SYMBOL, interval="1wk", strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME,
        evaluations=evaluations.evaluations,
    )
    with pytest.raises(StrategyAuditInputInvalidError):
        build_strategy_audit_evidence(market, bad_evaluations, outcomes, audit_date)


def test_strategy_id_mismatch_between_evaluation_and_outcome_rejected():
    market, evaluations, outcomes, dates, audit_date = _reference_fixture()
    bad_outcomes = compute_signal_outcomes(market, evaluations)
    bad_outcomes = type(bad_outcomes)(
        provider_symbol=bad_outcomes.provider_symbol, interval=bad_outcomes.interval,
        strategy_id="some_other_strategy", strategy_name=bad_outcomes.strategy_name, outcomes=bad_outcomes.outcomes,
    )
    with pytest.raises(StrategyAuditInputInvalidError):
        build_strategy_audit_evidence(market, evaluations, bad_outcomes, audit_date)


def test_row_count_mismatch_rejected():
    market, evaluations, outcomes, dates, audit_date = _reference_fixture()
    truncated_evaluations = StrategyEvaluationSeries(
        provider_symbol=SYMBOL, interval=INTERVAL, strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME,
        evaluations=evaluations.evaluations[:-1],
    )
    with pytest.raises(StrategyAuditInputInvalidError):
        build_strategy_audit_evidence(market, truncated_evaluations, outcomes, audit_date)


def test_date_misalignment_rejected():
    market, evaluations, outcomes, dates, audit_date = _reference_fixture()
    evals = list(evaluations.evaluations)
    shifted = evals[5]
    evals[5] = _evaluation(shifted.date + timedelta(days=1), shifted.decision)
    bad_evaluations = StrategyEvaluationSeries(
        provider_symbol=SYMBOL, interval=INTERVAL, strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME,
        evaluations=tuple(evals),
    )
    with pytest.raises(StrategyAuditInputInvalidError):
        build_strategy_audit_evidence(market, bad_evaluations, outcomes, audit_date)


def test_outcome_not_matching_a_buy_evaluation_rejected():
    market, evaluations, outcomes, dates, audit_date = _reference_fixture()
    # Fabricate an outcome dated at a NO_SIGNAL evaluation's date.
    no_signal_date = next(e.date for e in evaluations.evaluations if e.decision != StrategyDecision.BUY)
    fake_outcome = outcomes.outcomes[0]
    from app.outcomes.models import SignalOutcome

    bad = SignalOutcome(
        date=no_signal_date, decision=StrategyDecision.BUY, reference_close=fake_outcome.reference_close,
        forward_close_5d=None, forward_return_5d=None, forward_close_10d=None, forward_return_10d=None,
        mae_10d=None, mfe_10d=None, available_forward_bars=0,
    )
    bad_outcomes = type(outcomes)(
        provider_symbol=outcomes.provider_symbol, interval=outcomes.interval, strategy_id=outcomes.strategy_id,
        strategy_name=outcomes.strategy_name, outcomes=outcomes.outcomes + (bad,),
    )
    with pytest.raises(StrategyAuditInputInvalidError):
        build_strategy_audit_evidence(market, evaluations, bad_outcomes, audit_date)


def test_non_chronological_bars_rejected():
    dates = _dates(6)
    closes = [100.0 + i for i in range(6)]
    bars = [_bar(dates[0], closes[0]), _bar(dates[2], closes[2]), _bar(dates[1], closes[1])] + [
        _bar(dates[i], closes[i]) for i in range(3, 6)
    ]
    market = OHLCVSeries(provider_symbol=SYMBOL, interval=INTERVAL, bars=tuple(bars))
    evals = tuple(_evaluation(b.date, StrategyDecision.NO_SIGNAL) for b in bars)
    evaluations = StrategyEvaluationSeries(
        provider_symbol=SYMBOL, interval=INTERVAL, strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME, evaluations=evals
    )
    empty_outcomes = compute_signal_outcomes(
        OHLCVSeries(provider_symbol=SYMBOL, interval=INTERVAL, bars=tuple(sorted(bars, key=lambda b: b.date))),
        StrategyEvaluationSeries(
            provider_symbol=SYMBOL, interval=INTERVAL, strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME,
            evaluations=tuple(sorted(evals, key=lambda e: e.date)),
        ),
    )
    with pytest.raises(StrategyAuditInputInvalidError):
        build_strategy_audit_evidence(market, evaluations, empty_outcomes, dates[0])


# ---------------------------------------------------------------------------
# evidence_start_date: calculation history vs historical evidence window
# (Phase 3D correction -- see CLAUDE.md Phase 3D)
# ---------------------------------------------------------------------------


def test_evidence_start_date_excludes_prior_buys_before_it():
    market, evaluations, outcomes, dates, audit_date = _reference_fixture()
    # Reference fixture has prior BUYs at indices 2, 8, 13, 17 (audit at 18).
    # Restricting evidence_start_date to dates[10] excludes index 2 and 8,
    # leaving indices 13 and 17.
    evidence_start_date = dates[10]

    evidence = build_strategy_audit_evidence(market, evaluations, outcomes, audit_date, evidence_start_date)

    assert evidence.historical_evidence.prior_signal_count == 2  # indices 13 and 17
    assert evidence.historical_evidence.five_bar.eligible_outcome_count == 1  # index 13 only (5D-eligible)
    assert evidence.historical_evidence.ten_bar.eligible_outcome_count == 0  # neither is 10D-eligible


def test_evidence_start_date_none_matches_default_unrestricted_behavior():
    market, evaluations, outcomes, dates, audit_date = _reference_fixture()
    with_none = build_strategy_audit_evidence(market, evaluations, outcomes, audit_date, evidence_start_date=None)
    without_arg = build_strategy_audit_evidence(market, evaluations, outcomes, audit_date)
    assert with_none == without_arg


def test_evidence_start_date_does_not_require_an_exact_bar_match():
    """Unlike audit_date, evidence_start_date is a threshold comparison
    (signal_date >= evidence_start_date), not an exact-bar lookup -- a
    weekend/holiday value is valid and simply rounds forward."""
    market, evaluations, outcomes, dates, audit_date = _reference_fixture()
    near_miss = next(
        candidate
        for offset in range(1, 5)
        for candidate in (dates[10] + timedelta(days=offset), dates[10] - timedelta(days=offset))
        if candidate not in dates
    )
    # Must not raise, and must behave as the threshold >= near_miss.
    evidence = build_strategy_audit_evidence(market, evaluations, outcomes, audit_date, near_miss)
    assert evidence.historical_evidence.prior_signal_count in (0, 1, 2, 3, 4)  # no exception; a valid result


def test_evidence_start_date_does_not_affect_evaluation_or_retrospective_outcome():
    market, evaluations, outcomes, dates, audit_date = _reference_fixture()
    unrestricted = build_strategy_audit_evidence(market, evaluations, outcomes, audit_date)
    restricted = build_strategy_audit_evidence(market, evaluations, outcomes, audit_date, dates[15])

    assert unrestricted.evaluation == restricted.evaluation
    assert unrestricted.retrospective_outcome == restricted.retrospective_outcome

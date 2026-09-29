"""Phase 4A: historical BUY-signal investigation dataset engine tests.

Constructs `SignalOutcome`/`SignalOutcomeSeries` fixtures directly (the
accepted Phase 2A boundary this module consumes) rather than running the
full market-data/indicator/strategy pipeline -- Phase 4A never recomputes
any of that, so its tests exercise only the classification/population
transformation itself.
"""

from __future__ import annotations

import copy
from datetime import date

import pytest

from app.core.exceptions import InvestigationInputInvalidError
from app.investigation.engine import build_signal_investigation_dataset
from app.investigation.models import SignalInvestigationClassification
from app.outcomes.models import SignalOutcome, SignalOutcomeSeries
from app.strategies.models import StrategyDecision

SYMBOL = "X.NS"
INTERVAL = "1d"
STRATEGY_ID = "trend_momentum_v1"
STRATEGY_NAME = "Trend + Momentum v1"


def _full_outcome(
    d: date,
    forward_return_10d: float,
    *,
    reference_close: float = 100.0,
    forward_close_5d: float = 102.0,
    forward_return_5d: float = 0.02,
    mae_10d: float = -0.03,
    mfe_10d: float = 0.05,
    available_forward_bars: int = 15,
) -> SignalOutcome:
    """A fully-observable (10-bar-eligible) outcome."""
    return SignalOutcome(
        date=d,
        decision=StrategyDecision.BUY,
        reference_close=reference_close,
        forward_close_5d=forward_close_5d,
        forward_return_5d=forward_return_5d,
        forward_close_10d=reference_close * (1 + forward_return_10d),
        forward_return_10d=forward_return_10d,
        mae_10d=mae_10d,
        mfe_10d=mfe_10d,
        available_forward_bars=available_forward_bars,
    )


def _censored_outcome(
    d: date,
    *,
    reference_close: float = 100.0,
    forward_close_5d: float | None = None,
    forward_return_5d: float | None = None,
    available_forward_bars: int = 0,
) -> SignalOutcome:
    """An outcome with no complete 10-bar horizon -- may or may not have a
    5-bar outcome, per Phase 2A's independent 5D/10D availability."""
    return SignalOutcome(
        date=d,
        decision=StrategyDecision.BUY,
        reference_close=reference_close,
        forward_close_5d=forward_close_5d,
        forward_return_5d=forward_return_5d,
        forward_close_10d=None,
        forward_return_10d=None,
        mae_10d=None,
        mfe_10d=None,
        available_forward_bars=available_forward_bars,
    )


def _series(outcomes: tuple[SignalOutcome, ...]) -> SignalOutcomeSeries:
    return SignalOutcomeSeries(
        provider_symbol=SYMBOL, interval=INTERVAL, strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME, outcomes=outcomes
    )


# ---------------------------------------------------------------------------
# Classification boundaries (section 10)
# ---------------------------------------------------------------------------


def test_positive_return_classified_positive():
    dataset = build_signal_investigation_dataset(_series((_full_outcome(date(2024, 1, 1), 0.05),)))
    assert dataset.observations[0].classification == SignalInvestigationClassification.POSITIVE


def test_negative_return_classified_negative():
    dataset = build_signal_investigation_dataset(_series((_full_outcome(date(2024, 1, 1), -0.05),)))
    assert dataset.observations[0].classification == SignalInvestigationClassification.NEGATIVE


def test_exact_zero_return_classified_breakeven():
    dataset = build_signal_investigation_dataset(_series((_full_outcome(date(2024, 1, 1), 0.0),)))
    assert dataset.observations[0].classification == SignalInvestigationClassification.BREAKEVEN


def test_incomplete_10bar_horizon_classified_unavailable():
    dataset = build_signal_investigation_dataset(_series((_censored_outcome(date(2024, 1, 1)),)))
    assert dataset.observations[0].classification == SignalInvestigationClassification.UNAVAILABLE


def test_5d_available_but_10d_unavailable_still_classified_unavailable():
    outcome = _censored_outcome(date(2024, 1, 1), forward_close_5d=103.0, forward_return_5d=0.03, available_forward_bars=7)
    dataset = build_signal_investigation_dataset(_series((outcome,)))
    assert dataset.observations[0].classification == SignalInvestigationClassification.UNAVAILABLE


def test_tiny_positive_return_classified_positive_no_epsilon():
    dataset = build_signal_investigation_dataset(_series((_full_outcome(date(2024, 1, 1), 1e-12),)))
    assert dataset.observations[0].classification == SignalInvestigationClassification.POSITIVE


def test_tiny_negative_return_classified_negative_no_epsilon():
    dataset = build_signal_investigation_dataset(_series((_full_outcome(date(2024, 1, 1), -1e-12),)))
    assert dataset.observations[0].classification == SignalInvestigationClassification.NEGATIVE


# ---------------------------------------------------------------------------
# Value preservation (section 11)
# ---------------------------------------------------------------------------


def test_observation_preserves_all_phase2a_values_exactly():
    outcome = _full_outcome(
        date(2024, 3, 4),
        0.0684,
        reference_close=1465.25,
        forward_close_5d=1454.20,
        forward_return_5d=-0.0075,
        mae_10d=-0.0189,
        mfe_10d=0.0790,
        available_forward_bars=10,
    )
    observation = build_signal_investigation_dataset(_series((outcome,))).observations[0]

    assert observation.signal_date == date(2024, 3, 4)
    assert observation.reference_close == outcome.reference_close
    assert observation.forward_close_5d == outcome.forward_close_5d
    assert observation.forward_return_5d == outcome.forward_return_5d
    assert observation.forward_close_10d == outcome.forward_close_10d
    assert observation.forward_return_10d == outcome.forward_return_10d
    assert observation.mae_10d == outcome.mae_10d
    assert observation.mfe_10d == outcome.mfe_10d
    assert observation.available_forward_bars == outcome.available_forward_bars


def test_signed_mae_mfe_preserved_no_abs_no_percentage_conversion():
    outcome = _full_outcome(date(2024, 1, 1), -0.02, mae_10d=-0.0656, mfe_10d=0.1101)
    observation = build_signal_investigation_dataset(_series((outcome,))).observations[0]
    # Never abs()'d: MAE stays negative.
    assert observation.mae_10d == -0.0656
    # Never abs()'d/reinterpreted: MFE stays positive.
    assert observation.mfe_10d == 0.1101
    # Never *100: decimal fractions preserved exactly.
    assert observation.forward_return_10d == -0.02


# ---------------------------------------------------------------------------
# Population invariants (section 12)
# ---------------------------------------------------------------------------


def test_population_invariants_with_mixed_classifications():
    outcomes = (
        _full_outcome(date(2024, 1, 1), 0.05),
        _full_outcome(date(2024, 1, 2), 0.02),
        _full_outcome(date(2024, 1, 3), -0.03),
        _full_outcome(date(2024, 1, 4), 0.0),
        _censored_outcome(date(2024, 1, 5)),
        _censored_outcome(date(2024, 1, 6), forward_close_5d=101.0, forward_return_5d=0.01, available_forward_bars=6),
    )
    dataset = build_signal_investigation_dataset(_series(outcomes))

    assert dataset.total_signal_count == len(outcomes) == len(dataset.observations)
    assert dataset.positive_count == 2
    assert dataset.negative_count == 1
    assert dataset.breakeven_count == 1
    assert dataset.unavailable_count == 2
    assert dataset.eligible_count == dataset.positive_count + dataset.negative_count + dataset.breakeven_count
    assert dataset.total_signal_count == dataset.eligible_count + dataset.unavailable_count

    # Every input outcome maps to exactly one observation, in order.
    assert [o.signal_date for o in dataset.observations] == [o.date for o in outcomes]


def test_dataset_metadata_matches_source_series():
    dataset = build_signal_investigation_dataset(_series((_full_outcome(date(2024, 1, 1), 0.01),)))
    assert dataset.provider_symbol == SYMBOL
    assert dataset.interval == INTERVAL
    assert dataset.strategy_id == STRATEGY_ID
    assert dataset.strategy_name == STRATEGY_NAME


def test_empty_series_produces_empty_dataset_with_zeroed_counts():
    dataset = build_signal_investigation_dataset(_series(()))
    assert dataset.total_signal_count == 0
    assert dataset.eligible_count == 0
    assert dataset.positive_count == 0
    assert dataset.negative_count == 0
    assert dataset.breakeven_count == 0
    assert dataset.unavailable_count == 0
    assert dataset.observations == ()


# ---------------------------------------------------------------------------
# Censoring (section 13)
# ---------------------------------------------------------------------------


def test_censored_signals_remain_in_observations_and_only_affect_unavailable_count():
    outcomes = (
        _full_outcome(date(2024, 1, 1), 0.01),
        _censored_outcome(date(2024, 1, 2)),
        _censored_outcome(date(2024, 1, 3), forward_close_5d=99.0, forward_return_5d=-0.01),
    )
    dataset = build_signal_investigation_dataset(_series(outcomes))

    assert dataset.total_signal_count == 3
    assert len(dataset.observations) == 3
    censored = [o for o in dataset.observations if o.signal_date != date(2024, 1, 1)]
    assert len(censored) == 2
    assert all(o.classification == SignalInvestigationClassification.UNAVAILABLE for o in censored)

    assert dataset.unavailable_count == 2
    assert dataset.negative_count == 0
    assert dataset.positive_count == 1
    assert dataset.breakeven_count == 0
    assert dataset.eligible_count == 1  # only the one full-horizon observation


# ---------------------------------------------------------------------------
# Ordering / determinism (section 14)
# ---------------------------------------------------------------------------


def test_chronological_ordering_preserved_not_reordered_by_outcome():
    # Deliberately not sorted by return magnitude -- worst return first,
    # best return last -- to prove Phase 4A never reorders by outcome.
    outcomes = (
        _full_outcome(date(2024, 1, 1), -0.10),
        _full_outcome(date(2024, 1, 2), 0.01),
        _full_outcome(date(2024, 1, 3), 0.20),
    )
    dataset = build_signal_investigation_dataset(_series(outcomes))
    assert [o.signal_date for o in dataset.observations] == [date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3)]


def test_deterministic_repeated_execution():
    outcomes = (
        _full_outcome(date(2024, 1, 1), 0.05),
        _censored_outcome(date(2024, 1, 2)),
        _full_outcome(date(2024, 1, 3), -0.02),
    )
    series = _series(outcomes)
    first = build_signal_investigation_dataset(series)
    second = build_signal_investigation_dataset(series)
    assert first == second


def test_no_input_mutation():
    outcomes = (_full_outcome(date(2024, 1, 1), 0.05), _censored_outcome(date(2024, 1, 2)))
    series = _series(outcomes)
    before = copy.deepcopy(series)
    build_signal_investigation_dataset(series)
    assert series == before


# ---------------------------------------------------------------------------
# Structural errors (section 15)
# ---------------------------------------------------------------------------


def test_non_buy_decision_outcome_rejected():
    bad_outcome = SignalOutcome(
        date=date(2024, 1, 1),
        decision=StrategyDecision.NO_SIGNAL,  # structurally impossible per Phase 2A's own contract
        reference_close=100.0,
        forward_close_5d=None,
        forward_return_5d=None,
        forward_close_10d=None,
        forward_return_10d=None,
        mae_10d=None,
        mfe_10d=None,
        available_forward_bars=0,
    )
    with pytest.raises(InvestigationInputInvalidError):
        build_signal_investigation_dataset(_series((bad_outcome,)))


def test_full_10d_return_present_but_mae_missing_rejected():
    bad_outcome = SignalOutcome(
        date=date(2024, 1, 1),
        decision=StrategyDecision.BUY,
        reference_close=100.0,
        forward_close_5d=102.0,
        forward_return_5d=0.02,
        forward_close_10d=105.0,
        forward_return_10d=0.05,
        mae_10d=None,  # inconsistent: 10D return present but MAE missing
        mfe_10d=0.06,
        available_forward_bars=15,
    )
    with pytest.raises(InvestigationInputInvalidError):
        build_signal_investigation_dataset(_series((bad_outcome,)))


def test_full_10d_return_present_but_mfe_missing_rejected():
    bad_outcome = SignalOutcome(
        date=date(2024, 1, 1),
        decision=StrategyDecision.BUY,
        reference_close=100.0,
        forward_close_5d=102.0,
        forward_return_5d=0.02,
        forward_close_10d=105.0,
        forward_return_10d=0.05,
        mae_10d=-0.02,
        mfe_10d=None,  # inconsistent: 10D return present but MFE missing
        available_forward_bars=15,
    )
    with pytest.raises(InvestigationInputInvalidError):
        build_signal_investigation_dataset(_series((bad_outcome,)))


def test_10d_close_present_but_return_missing_rejected():
    bad_outcome = SignalOutcome(
        date=date(2024, 1, 1),
        decision=StrategyDecision.BUY,
        reference_close=100.0,
        forward_close_5d=102.0,
        forward_return_5d=0.02,
        forward_close_10d=105.0,
        forward_return_10d=None,  # inconsistent: close present but return missing
        mae_10d=-0.02,
        mfe_10d=0.06,
        available_forward_bars=15,
    )
    with pytest.raises(InvestigationInputInvalidError):
        build_signal_investigation_dataset(_series((bad_outcome,)))


def test_non_finite_forward_return_10d_rejected():
    bad_outcome = SignalOutcome(
        date=date(2024, 1, 1),
        decision=StrategyDecision.BUY,
        reference_close=100.0,
        forward_close_5d=102.0,
        forward_return_5d=0.02,
        forward_close_10d=105.0,
        forward_return_10d=float("nan"),
        mae_10d=-0.02,
        mfe_10d=0.06,
        available_forward_bars=15,
    )
    with pytest.raises(InvestigationInputInvalidError):
        build_signal_investigation_dataset(_series((bad_outcome,)))


def test_malformed_observation_does_not_get_silently_skipped_or_zeroed():
    # A single malformed outcome anywhere in the series must abort the
    # whole build with an explicit error -- never silently dropped and
    # never substituted with a zero/UNAVAILABLE result.
    outcomes = (
        _full_outcome(date(2024, 1, 1), 0.05),
        SignalOutcome(
            date=date(2024, 1, 2),
            decision=StrategyDecision.BUY,
            reference_close=100.0,
            forward_close_5d=None,
            forward_return_5d=None,
            forward_close_10d=100.0,
            forward_return_10d=0.0,
            mae_10d=None,
            mfe_10d=None,
            available_forward_bars=10,
        ),
    )
    with pytest.raises(InvestigationInputInvalidError):
        build_signal_investigation_dataset(_series(outcomes))

"""Phase 4B: FAILED / NON_FAILED population comparison engine tests.

Constructs `SignalInvestigationDataset`/`SignalInvestigationObservation`
fixtures directly (the accepted Phase 4A boundary this module consumes)
rather than running the full Phase 2A/4A pipeline. Expected arithmetic
values are calculated independently by hand (see comments), never by
calling `statistics`/`sum`/`min`/`max` a second time inside the assertions
in a way that would merely mirror the implementation.
"""

from __future__ import annotations

import copy
import math
from datetime import date

import pytest

from app.core.exceptions import InvestigationInputInvalidError
from app.investigation.comparison import build_failure_population_comparison
from app.investigation.models import SignalInvestigationClassification, SignalInvestigationDataset, SignalInvestigationObservation

SYMBOL = "X.NS"
INTERVAL = "1d"
STRATEGY_ID = "trend_momentum_v1"
STRATEGY_NAME = "Trend + Momentum v1"

POSITIVE = SignalInvestigationClassification.POSITIVE
NEGATIVE = SignalInvestigationClassification.NEGATIVE
BREAKEVEN = SignalInvestigationClassification.BREAKEVEN
UNAVAILABLE = SignalInvestigationClassification.UNAVAILABLE


def _obs(
    d: date,
    classification: SignalInvestigationClassification,
    *,
    forward_return_10d: float | None = None,
    mae_10d: float | None = None,
    mfe_10d: float | None = None,
    reference_close: float = 100.0,
    forward_close_5d: float | None = 101.0,
    forward_return_5d: float | None = 0.01,
    available_forward_bars: int = 15,
) -> SignalInvestigationObservation:
    forward_close_10d = None if forward_return_10d is None else reference_close * (1 + forward_return_10d)
    return SignalInvestigationObservation(
        signal_date=d,
        classification=classification,
        reference_close=reference_close,
        forward_close_5d=forward_close_5d,
        forward_return_5d=forward_return_5d,
        forward_close_10d=forward_close_10d,
        forward_return_10d=forward_return_10d,
        mae_10d=mae_10d,
        mfe_10d=mfe_10d,
        available_forward_bars=available_forward_bars,
    )


def _dataset(observations: tuple[SignalInvestigationObservation, ...]) -> SignalInvestigationDataset:
    """Builds a *consistent* Phase 4A dataset fixture from observations,
    computing declared counts the same way a caller supplying real Phase 4A
    output would have them already set -- this is fixture construction, not
    the code under test (which is `build_failure_population_comparison`,
    not this counting)."""
    positive = sum(1 for o in observations if o.classification == POSITIVE)
    negative = sum(1 for o in observations if o.classification == NEGATIVE)
    breakeven = sum(1 for o in observations if o.classification == BREAKEVEN)
    unavailable = sum(1 for o in observations if o.classification == UNAVAILABLE)
    return SignalInvestigationDataset(
        provider_symbol=SYMBOL,
        interval=INTERVAL,
        strategy_id=STRATEGY_ID,
        strategy_name=STRATEGY_NAME,
        observations=observations,
        total_signal_count=len(observations),
        eligible_count=positive + negative + breakeven,
        positive_count=positive,
        negative_count=negative,
        breakeven_count=breakeven,
        unavailable_count=unavailable,
    )


# ---------------------------------------------------------------------------
# Main mixed fixture (used by several tests below).
#
# FAILED (NEGATIVE), 3 observations (odd count):
#   returns: -0.05, -0.02, -0.10   -> sorted [-0.10, -0.05, -0.02] -> median -0.05
#   sum = -0.17 -> average = -0.17 / 3
#   mae:     -0.08, -0.03, -0.12   -> sorted [-0.12, -0.08, -0.03] -> median -0.08, worst(min) -0.12
#   sum = -0.23 -> average = -0.23 / 3
#   mfe:      0.01,  0.04,  0.02   -> sorted [0.01, 0.02, 0.04] -> median 0.02, best(max) 0.04
#   sum = 0.07 -> average = 0.07 / 3
#
# NON_FAILED (POSITIVE x3 + BREAKEVEN x1), 4 observations (even count):
#   returns: 0.03, 0.08, 0.01, 0.0 -> sorted [0.0, 0.01, 0.03, 0.08] -> median (0.01+0.03)/2 = 0.02
#   sum = 0.12 -> average = 0.12 / 4 = 0.03
#   mae:    -0.01, -0.02, -0.005, -0.015 -> sorted [-0.02, -0.015, -0.01, -0.005] -> median (-0.015-0.01)/2 = -0.0125, worst(min) -0.02
#   sum = -0.05 -> average = -0.05 / 4 = -0.0125
#   mfe:     0.05,  0.10,  0.02,   0.03  -> sorted [0.02, 0.03, 0.05, 0.10] -> median (0.03+0.05)/2 = 0.04, best(max) 0.10
#   sum = 0.20 -> average = 0.20 / 4 = 0.05
#
# UNAVAILABLE: 2 observations, excluded entirely.
# ---------------------------------------------------------------------------


def _mixed_observations() -> tuple[SignalInvestigationObservation, ...]:
    return (
        _obs(date(2024, 1, 1), NEGATIVE, forward_return_10d=-0.05, mae_10d=-0.08, mfe_10d=0.01),
        _obs(date(2024, 1, 2), NEGATIVE, forward_return_10d=-0.02, mae_10d=-0.03, mfe_10d=0.04),
        _obs(date(2024, 1, 3), NEGATIVE, forward_return_10d=-0.10, mae_10d=-0.12, mfe_10d=0.02),
        _obs(date(2024, 1, 4), POSITIVE, forward_return_10d=0.03, mae_10d=-0.01, mfe_10d=0.05),
        _obs(date(2024, 1, 5), POSITIVE, forward_return_10d=0.08, mae_10d=-0.02, mfe_10d=0.10),
        _obs(date(2024, 1, 6), POSITIVE, forward_return_10d=0.01, mae_10d=-0.005, mfe_10d=0.02),
        _obs(date(2024, 1, 7), BREAKEVEN, forward_return_10d=0.0, mae_10d=-0.015, mfe_10d=0.03),
        _obs(date(2024, 1, 8), UNAVAILABLE),
        _obs(date(2024, 1, 9), UNAVAILABLE),
    )


def _mixed_dataset() -> SignalInvestigationDataset:
    return _dataset(_mixed_observations())


# ---------------------------------------------------------------------------
# 1-4: membership
# ---------------------------------------------------------------------------


def test_negative_observations_belong_to_failed_population():
    result = build_failure_population_comparison(_mixed_dataset())
    assert result.failed.count == 3


def test_positive_observations_belong_to_non_failed_population():
    dataset = _dataset((_obs(date(2024, 1, 1), POSITIVE, forward_return_10d=0.05, mae_10d=-0.01, mfe_10d=0.06),))
    result = build_failure_population_comparison(dataset)
    assert result.non_failed.count == 1
    assert result.failed.count == 0


def test_breakeven_belongs_to_non_failed_not_failed():
    dataset = _dataset((_obs(date(2024, 1, 1), BREAKEVEN, forward_return_10d=0.0, mae_10d=-0.01, mfe_10d=0.02),))
    result = build_failure_population_comparison(dataset)
    assert result.non_failed.count == 1
    assert result.failed.count == 0


def test_unavailable_belongs_to_neither_population():
    dataset = _dataset((_obs(date(2024, 1, 1), UNAVAILABLE),))
    result = build_failure_population_comparison(dataset)
    assert result.failed.count == 0
    assert result.non_failed.count == 0
    assert result.eligible_count == 0
    assert result.unavailable_count == 1


# ---------------------------------------------------------------------------
# 5: population-count invariants (against the authoritative Phase 4A counts)
# ---------------------------------------------------------------------------


def test_population_count_invariants_against_source_dataset():
    dataset = _mixed_dataset()
    result = build_failure_population_comparison(dataset)

    assert result.failed.count == dataset.negative_count
    assert result.non_failed.count == dataset.positive_count + dataset.breakeven_count
    assert result.eligible_count == result.failed.count + result.non_failed.count
    assert result.total_signal_count == result.eligible_count + result.unavailable_count
    assert result.total_signal_count == dataset.total_signal_count
    assert result.unavailable_count == dataset.unavailable_count


# ---------------------------------------------------------------------------
# 6-8: mean/median correctness (hand-derived, see comment block above)
# ---------------------------------------------------------------------------


def test_failed_population_mean_and_odd_count_median():
    result = build_failure_population_comparison(_mixed_dataset())
    failed = result.failed

    assert failed.average_forward_return_10d == pytest.approx(-0.17 / 3)
    assert failed.median_forward_return_10d == pytest.approx(-0.05)
    assert failed.average_mae_10d == pytest.approx(-0.23 / 3)
    assert failed.median_mae_10d == pytest.approx(-0.08)
    assert failed.average_mfe_10d == pytest.approx(0.07 / 3)
    assert failed.median_mfe_10d == pytest.approx(0.02)


def test_non_failed_population_mean_and_even_count_median():
    result = build_failure_population_comparison(_mixed_dataset())
    non_failed = result.non_failed

    assert non_failed.average_forward_return_10d == pytest.approx(0.03)
    assert non_failed.median_forward_return_10d == pytest.approx((0.01 + 0.03) / 2)
    assert non_failed.average_mae_10d == pytest.approx(-0.0125)
    assert non_failed.median_mae_10d == pytest.approx((-0.015 + -0.01) / 2)
    assert non_failed.average_mfe_10d == pytest.approx(0.05)
    assert non_failed.median_mfe_10d == pytest.approx((0.03 + 0.05) / 2)


# ---------------------------------------------------------------------------
# 9-12: signed MAE/MFE preservation, worst/best selection
# ---------------------------------------------------------------------------


def test_signed_mae_preserved_and_worst_is_minimum_signed_value():
    result = build_failure_population_comparison(_mixed_dataset())
    # Worst MAE across the FAILED population's [-0.08, -0.03, -0.12] is the
    # most negative value, -0.12 -- never abs()'d/reinterpreted as "largest
    # magnitude via abs()" (which would coincidentally also be -0.12 here,
    # so also exercise the NON_FAILED population where abs() would give a
    # different, wrong answer than min()).
    assert result.failed.worst_mae_10d == pytest.approx(-0.12)
    # NON_FAILED MAEs: [-0.01, -0.02, -0.005, -0.015]. abs()-based "worst"
    # would wrongly pick -0.02 as well here by coincidence of sign, so also
    # check the actual minimum directly: min() of these signed values is
    # -0.02, which matches -- but critically the value stays NEGATIVE, not
    # abs()'d to 0.02.
    assert result.non_failed.worst_mae_10d == pytest.approx(-0.02)
    assert result.non_failed.worst_mae_10d < 0


def test_signed_mfe_preserved_and_best_is_maximum_signed_value():
    result = build_failure_population_comparison(_mixed_dataset())
    assert result.failed.best_mfe_10d == pytest.approx(0.04)
    assert result.non_failed.best_mfe_10d == pytest.approx(0.10)
    assert result.failed.best_mfe_10d > 0
    assert result.non_failed.best_mfe_10d > 0


def test_negative_mfe_stays_negative_not_abs():
    # A population where MFE itself is negative (the whole forward window
    # traded below reference) must keep that sign -- proves no abs().
    dataset = _dataset((_obs(date(2024, 1, 1), NEGATIVE, forward_return_10d=-0.05, mae_10d=-0.09, mfe_10d=-0.01),))
    result = build_failure_population_comparison(dataset)
    assert result.failed.best_mfe_10d == pytest.approx(-0.01)
    assert result.failed.average_mfe_10d == pytest.approx(-0.01)


def test_positive_mae_stays_positive_not_forced_negative():
    # A population where MAE itself is positive (the whole forward window
    # traded above reference) must keep that sign.
    dataset = _dataset((_obs(date(2024, 1, 1), POSITIVE, forward_return_10d=0.05, mae_10d=0.01, mfe_10d=0.09),))
    result = build_failure_population_comparison(dataset)
    assert result.non_failed.worst_mae_10d == pytest.approx(0.01)
    assert result.non_failed.average_mae_10d == pytest.approx(0.01)


# ---------------------------------------------------------------------------
# 13-14: no percentage conversion, no rounding
# ---------------------------------------------------------------------------


def test_no_percentage_conversion_values_stay_decimal_fractions():
    dataset = _dataset((_obs(date(2024, 1, 1), POSITIVE, forward_return_10d=0.0684, mae_10d=-0.0189, mfe_10d=0.0790),))
    result = build_failure_population_comparison(dataset)
    assert result.non_failed.average_forward_return_10d == pytest.approx(0.0684)
    assert result.non_failed.average_forward_return_10d < 1  # never *100 (would be 6.84)


def test_no_rounding_full_precision_preserved():
    precise_return = 0.06835012756462211
    dataset = _dataset((_obs(date(2024, 1, 1), POSITIVE, forward_return_10d=precise_return, mae_10d=-0.018938747653983956, mfe_10d=0.07899675823238361),))
    result = build_failure_population_comparison(dataset)
    assert result.non_failed.average_forward_return_10d == precise_return
    assert result.non_failed.median_forward_return_10d == precise_return


# ---------------------------------------------------------------------------
# 15-18: empty populations / single observation
# ---------------------------------------------------------------------------


def test_empty_failed_population_all_none():
    dataset = _dataset((_obs(date(2024, 1, 1), POSITIVE, forward_return_10d=0.05, mae_10d=-0.01, mfe_10d=0.06),))
    result = build_failure_population_comparison(dataset)
    assert result.failed.count == 0
    assert result.failed.average_forward_return_10d is None
    assert result.failed.median_forward_return_10d is None
    assert result.failed.average_mae_10d is None
    assert result.failed.median_mae_10d is None
    assert result.failed.worst_mae_10d is None
    assert result.failed.average_mfe_10d is None
    assert result.failed.median_mfe_10d is None
    assert result.failed.best_mfe_10d is None


def test_empty_non_failed_population_all_none():
    dataset = _dataset((_obs(date(2024, 1, 1), NEGATIVE, forward_return_10d=-0.05, mae_10d=-0.08, mfe_10d=0.01),))
    result = build_failure_population_comparison(dataset)
    assert result.non_failed.count == 0
    assert result.non_failed.average_forward_return_10d is None
    assert result.non_failed.median_mae_10d is None
    assert result.non_failed.best_mfe_10d is None


def test_completely_empty_dataset_produces_valid_empty_comparison():
    dataset = _dataset(())
    result = build_failure_population_comparison(dataset)
    assert result.total_signal_count == 0
    assert result.eligible_count == 0
    assert result.unavailable_count == 0
    assert result.failed.count == 0
    assert result.non_failed.count == 0
    assert result.failed.average_forward_return_10d is None
    assert result.non_failed.average_forward_return_10d is None


def test_single_observation_population_median_equals_the_value_itself():
    dataset = _dataset((_obs(date(2024, 1, 1), NEGATIVE, forward_return_10d=-0.07, mae_10d=-0.09, mfe_10d=0.02),))
    result = build_failure_population_comparison(dataset)
    assert result.failed.count == 1
    assert result.failed.average_forward_return_10d == pytest.approx(-0.07)
    assert result.failed.median_forward_return_10d == pytest.approx(-0.07)
    assert result.failed.worst_mae_10d == pytest.approx(-0.09)
    assert result.failed.best_mfe_10d == pytest.approx(0.02)


# ---------------------------------------------------------------------------
# 19-20: determinism / non-mutation
# ---------------------------------------------------------------------------


def test_deterministic_repeated_execution():
    dataset = _mixed_dataset()
    first = build_failure_population_comparison(dataset)
    second = build_failure_population_comparison(dataset)
    assert first == second


def test_no_input_mutation():
    dataset = _mixed_dataset()
    before = copy.deepcopy(dataset)
    build_failure_population_comparison(dataset)
    assert dataset == before


# ---------------------------------------------------------------------------
# 21-26: structural errors
# ---------------------------------------------------------------------------


def test_eligible_observation_missing_return_rejected():
    dataset = _dataset((_obs(date(2024, 1, 1), NEGATIVE, forward_return_10d=None, mae_10d=-0.08, mfe_10d=0.01),))
    with pytest.raises(InvestigationInputInvalidError):
        build_failure_population_comparison(dataset)


def test_eligible_observation_missing_mae_rejected():
    dataset = _dataset((_obs(date(2024, 1, 1), NEGATIVE, forward_return_10d=-0.05, mae_10d=None, mfe_10d=0.01),))
    with pytest.raises(InvestigationInputInvalidError):
        build_failure_population_comparison(dataset)


def test_eligible_observation_missing_mfe_rejected():
    dataset = _dataset((_obs(date(2024, 1, 1), POSITIVE, forward_return_10d=0.05, mae_10d=-0.01, mfe_10d=None),))
    with pytest.raises(InvestigationInputInvalidError):
        build_failure_population_comparison(dataset)


def test_non_finite_return_rejected():
    dataset = _dataset((_obs(date(2024, 1, 1), POSITIVE, forward_return_10d=math.nan, mae_10d=-0.01, mfe_10d=0.05),))
    with pytest.raises(InvestigationInputInvalidError):
        build_failure_population_comparison(dataset)


def test_non_finite_mae_rejected():
    dataset = _dataset((_obs(date(2024, 1, 1), NEGATIVE, forward_return_10d=-0.05, mae_10d=math.inf, mfe_10d=0.01),))
    with pytest.raises(InvestigationInputInvalidError):
        build_failure_population_comparison(dataset)


def test_non_finite_mfe_rejected():
    dataset = _dataset((_obs(date(2024, 1, 1), POSITIVE, forward_return_10d=0.05, mae_10d=-0.01, mfe_10d=-math.inf),))
    with pytest.raises(InvestigationInputInvalidError):
        build_failure_population_comparison(dataset)


def test_mismatched_negative_count_rejected():
    good = _mixed_dataset()
    tampered = SignalInvestigationDataset(
        provider_symbol=good.provider_symbol,
        interval=good.interval,
        strategy_id=good.strategy_id,
        strategy_name=good.strategy_name,
        observations=good.observations,
        total_signal_count=good.total_signal_count,
        eligible_count=good.eligible_count,
        positive_count=good.positive_count,
        negative_count=good.negative_count + 1,  # inconsistent with actual observations
        breakeven_count=good.breakeven_count,
        unavailable_count=good.unavailable_count,
    )
    with pytest.raises(InvestigationInputInvalidError):
        build_failure_population_comparison(tampered)


def test_mismatched_total_signal_count_rejected():
    good = _mixed_dataset()
    tampered = SignalInvestigationDataset(
        provider_symbol=good.provider_symbol,
        interval=good.interval,
        strategy_id=good.strategy_id,
        strategy_name=good.strategy_name,
        observations=good.observations,
        total_signal_count=good.total_signal_count + 5,  # inconsistent
        eligible_count=good.eligible_count,
        positive_count=good.positive_count,
        negative_count=good.negative_count,
        breakeven_count=good.breakeven_count,
        unavailable_count=good.unavailable_count,
    )
    with pytest.raises(InvestigationInputInvalidError):
        build_failure_population_comparison(tampered)

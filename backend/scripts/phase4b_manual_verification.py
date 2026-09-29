"""Phase 4B manual acceptance helper (not a test -- run manually).

Builds a hand-constructed Phase 2A `SignalOutcomeSeries` fixture (5 NEGATIVE,
3 POSITIVE, 1 BREAKEVEN, 1 UNAVAILABLE), runs it through the accepted Phase
4A classification engine and then the Phase 4B comparison engine, prints
both the source population and the FAILED/NON_FAILED comparison summaries,
and independently asserts hand-verified expected arithmetic (mean, median,
worst/best MAE/MFE) for both populations -- it does not merely print
whatever the production code happens to compute.

No network. No FastAPI/Pydantic. Run with:

    cd backend
    PYTHONPATH=. python scripts/phase4b_manual_verification.py
"""

from __future__ import annotations

import math
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.investigation.comparison import build_failure_population_comparison
from app.investigation.engine import build_signal_investigation_dataset
from app.outcomes.models import SignalOutcome, SignalOutcomeSeries
from app.strategies.models import StrategyDecision

SYMBOL = "RELIANCE.NS"
INTERVAL = "1d"
STRATEGY_ID = "trend_momentum_v1"
STRATEGY_NAME = "Trend + Momentum v1"


def _buy(d: date, forward_return_10d: float | None, mae_10d: float | None, mfe_10d: float | None, available_forward_bars: int) -> SignalOutcome:
    reference_close = 100.0
    forward_close_10d = None if forward_return_10d is None else reference_close * (1 + forward_return_10d)
    return SignalOutcome(
        date=d,
        decision=StrategyDecision.BUY,
        reference_close=reference_close,
        forward_close_5d=reference_close * 1.01 if forward_return_10d is not None else None,
        forward_return_5d=0.01 if forward_return_10d is not None else None,
        forward_close_10d=forward_close_10d,
        forward_return_10d=forward_return_10d,
        mae_10d=mae_10d,
        mfe_10d=mfe_10d,
        available_forward_bars=available_forward_bars,
    )


# --- FAILED (NEGATIVE) population: 5 observations (odd count) -------------
# returns: -0.01, -0.03, -0.02, -0.06, -0.04
# sorted:  [-0.06, -0.04, -0.03, -0.02, -0.01] -> median (3rd of 5) = -0.03
# sum = -0.16 -> average = -0.032
#
# mae:     -0.05, -0.07, -0.04, -0.10, -0.06
# sorted:  [-0.10, -0.07, -0.06, -0.05, -0.04] -> median = -0.06, worst(min) = -0.10
# sum = -0.32 -> average = -0.064
#
# mfe:      0.01,  0.02,  0.015, 0.005, 0.03
# sorted:  [0.005, 0.01, 0.015, 0.02, 0.03] -> median = 0.015, best(max) = 0.03
# sum = 0.08 -> average = 0.016
NEGATIVE_FIXTURES = [
    (date(2024, 1, 2), -0.01, -0.05, 0.01),
    (date(2024, 1, 3), -0.03, -0.07, 0.02),
    (date(2024, 1, 4), -0.02, -0.04, 0.015),
    (date(2024, 1, 5), -0.06, -0.10, 0.005),
    (date(2024, 1, 8), -0.04, -0.06, 0.03),
]
EXPECTED_FAILED_AVERAGE_RETURN = -0.16 / 5
EXPECTED_FAILED_MEDIAN_RETURN = -0.03
EXPECTED_FAILED_AVERAGE_MAE = -0.32 / 5
EXPECTED_FAILED_MEDIAN_MAE = -0.06
EXPECTED_FAILED_WORST_MAE = -0.10
EXPECTED_FAILED_AVERAGE_MFE = 0.08 / 5
EXPECTED_FAILED_MEDIAN_MFE = 0.015
EXPECTED_FAILED_BEST_MFE = 0.03

# --- NON_FAILED (POSITIVE x3 + BREAKEVEN x1) population: 4 obs (even) -----
# returns: 0.05, 0.02, 0.09 (POSITIVE), 0.0 (BREAKEVEN)
# sorted:  [0.0, 0.02, 0.05, 0.09] -> median = (0.02 + 0.05) / 2 = 0.035
# sum = 0.16 -> average = 0.04
#
# mae:     -0.01, -0.015, -0.02 (POSITIVE), -0.008 (BREAKEVEN)
# sorted:  [-0.02, -0.015, -0.01, -0.008] -> median = (-0.015 + -0.01) / 2 = -0.0125, worst(min) = -0.02
# sum = -0.053 -> average = -0.01325
#
# mfe:      0.06, 0.03, 0.12 (POSITIVE), 0.02 (BREAKEVEN)
# sorted:  [0.02, 0.03, 0.06, 0.12] -> median = (0.03 + 0.06) / 2 = 0.045, best(max) = 0.12
# sum = 0.23 -> average = 0.0575
POSITIVE_FIXTURES = [
    (date(2024, 1, 9), 0.05, -0.01, 0.06),
    (date(2024, 1, 10), 0.02, -0.015, 0.03),
    (date(2024, 1, 11), 0.09, -0.02, 0.12),
]
BREAKEVEN_FIXTURE = (date(2024, 1, 12), 0.0, -0.008, 0.02)
EXPECTED_NON_FAILED_AVERAGE_RETURN = 0.16 / 4
EXPECTED_NON_FAILED_MEDIAN_RETURN = (0.02 + 0.05) / 2
EXPECTED_NON_FAILED_AVERAGE_MAE = -0.053 / 4
EXPECTED_NON_FAILED_MEDIAN_MAE = (-0.015 + -0.01) / 2
EXPECTED_NON_FAILED_WORST_MAE = -0.02
EXPECTED_NON_FAILED_AVERAGE_MFE = 0.23 / 4
EXPECTED_NON_FAILED_MEDIAN_MFE = (0.03 + 0.06) / 2
EXPECTED_NON_FAILED_BEST_MFE = 0.12

UNAVAILABLE_FIXTURE = date(2024, 1, 15)  # no complete 10-bar outcome


def build_outcome_series() -> SignalOutcomeSeries:
    outcomes = [_buy(d, ret, mae, mfe, available_forward_bars=25) for d, ret, mae, mfe in NEGATIVE_FIXTURES]
    outcomes += [_buy(d, ret, mae, mfe, available_forward_bars=25) for d, ret, mae, mfe in POSITIVE_FIXTURES]
    outcomes.append(_buy(*BREAKEVEN_FIXTURE, available_forward_bars=25))
    outcomes.append(_buy(UNAVAILABLE_FIXTURE, None, None, None, available_forward_bars=4))
    outcomes.sort(key=lambda o: o.date)
    return SignalOutcomeSeries(
        provider_symbol=SYMBOL, interval=INTERVAL, strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME, outcomes=tuple(outcomes)
    )


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:+.6f}"


def _check(label: str, actual: float | None, expected: float) -> None:
    assert actual is not None, f"{label}: expected {expected!r}, got None"
    assert math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12), f"{label}: expected {expected!r}, got {actual!r}"
    print(f"  [OK] {label}: {actual!r} == {expected!r}")


def main() -> None:
    outcome_series = build_outcome_series()
    dataset = build_signal_investigation_dataset(outcome_series)
    comparison = build_failure_population_comparison(dataset)

    print("SOURCE POPULATION")
    print(f"  total:        {dataset.total_signal_count}")
    print(f"  positive:     {dataset.positive_count}")
    print(f"  negative:     {dataset.negative_count}")
    print(f"  breakeven:    {dataset.breakeven_count}")
    print(f"  unavailable:  {dataset.unavailable_count}")
    print()

    print("FAILED POPULATION")
    f = comparison.failed
    print(f"  count:                 {f.count}")
    print(f"  average 10D return:    {_fmt(f.average_forward_return_10d)}")
    print(f"  median 10D return:     {_fmt(f.median_forward_return_10d)}")
    print(f"  average MAE:           {_fmt(f.average_mae_10d)}")
    print(f"  median MAE:            {_fmt(f.median_mae_10d)}")
    print(f"  worst MAE:             {_fmt(f.worst_mae_10d)}")
    print(f"  average MFE:           {_fmt(f.average_mfe_10d)}")
    print(f"  median MFE:            {_fmt(f.median_mfe_10d)}")
    print(f"  best MFE:              {_fmt(f.best_mfe_10d)}")
    print()

    print("NON-FAILED POPULATION")
    nf = comparison.non_failed
    print(f"  count:                 {nf.count}")
    print(f"  average 10D return:    {_fmt(nf.average_forward_return_10d)}")
    print(f"  median 10D return:     {_fmt(nf.median_forward_return_10d)}")
    print(f"  average MAE:           {_fmt(nf.average_mae_10d)}")
    print(f"  median MAE:            {_fmt(nf.median_mae_10d)}")
    print(f"  worst MAE:             {_fmt(nf.worst_mae_10d)}")
    print(f"  average MFE:           {_fmt(nf.average_mfe_10d)}")
    print(f"  median MFE:            {_fmt(nf.median_mfe_10d)}")
    print(f"  best MFE:              {_fmt(nf.best_mfe_10d)}")
    print()

    # --- Population-count invariants -------------------------------------
    assert dataset.total_signal_count == 10
    assert dataset.negative_count == 5
    assert dataset.positive_count == 3
    assert dataset.breakeven_count == 1
    assert dataset.unavailable_count == 1
    assert comparison.failed.count == dataset.negative_count
    assert comparison.non_failed.count == dataset.positive_count + dataset.breakeven_count
    assert comparison.eligible_count == comparison.failed.count + comparison.non_failed.count
    assert comparison.total_signal_count == comparison.eligible_count + comparison.unavailable_count
    print("Population-count invariants hold.")
    print()

    # --- Independently hand-verified arithmetic ---------------------------
    print("Checking FAILED population arithmetic against hand-derived expected values:")
    _check("average_forward_return_10d", f.average_forward_return_10d, EXPECTED_FAILED_AVERAGE_RETURN)
    _check("median_forward_return_10d", f.median_forward_return_10d, EXPECTED_FAILED_MEDIAN_RETURN)
    _check("average_mae_10d", f.average_mae_10d, EXPECTED_FAILED_AVERAGE_MAE)
    _check("median_mae_10d", f.median_mae_10d, EXPECTED_FAILED_MEDIAN_MAE)
    _check("worst_mae_10d", f.worst_mae_10d, EXPECTED_FAILED_WORST_MAE)
    _check("average_mfe_10d", f.average_mfe_10d, EXPECTED_FAILED_AVERAGE_MFE)
    _check("median_mfe_10d", f.median_mfe_10d, EXPECTED_FAILED_MEDIAN_MFE)
    _check("best_mfe_10d", f.best_mfe_10d, EXPECTED_FAILED_BEST_MFE)
    print()

    print("Checking NON-FAILED population arithmetic against hand-derived expected values:")
    _check("average_forward_return_10d", nf.average_forward_return_10d, EXPECTED_NON_FAILED_AVERAGE_RETURN)
    _check("median_forward_return_10d", nf.median_forward_return_10d, EXPECTED_NON_FAILED_MEDIAN_RETURN)
    _check("average_mae_10d", nf.average_mae_10d, EXPECTED_NON_FAILED_AVERAGE_MAE)
    _check("median_mae_10d", nf.median_mae_10d, EXPECTED_NON_FAILED_MEDIAN_MAE)
    _check("worst_mae_10d", nf.worst_mae_10d, EXPECTED_NON_FAILED_WORST_MAE)
    _check("average_mfe_10d", nf.average_mfe_10d, EXPECTED_NON_FAILED_AVERAGE_MFE)
    _check("median_mfe_10d", nf.median_mfe_10d, EXPECTED_NON_FAILED_MEDIAN_MFE)
    _check("best_mfe_10d", nf.best_mfe_10d, EXPECTED_NON_FAILED_BEST_MFE)
    print()

    # Signed-value sanity: MAE stays negative, MFE stays positive here --
    # never abs()'d.
    assert f.worst_mae_10d is not None
    assert nf.worst_mae_10d is not None
    assert f.best_mfe_10d is not None
    assert nf.best_mfe_10d is not None
    assert f.worst_mae_10d < 0 and nf.worst_mae_10d < 0
    assert f.best_mfe_10d > 0 and nf.best_mfe_10d > 0

    print("ALL MANUAL PHASE 4B CHECKS PASSED")


if __name__ == "__main__":
    main()

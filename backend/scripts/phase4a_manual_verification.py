"""Phase 4A manual acceptance helper (not a test -- run manually).

Builds a small, hand-constructed Phase 2A `SignalOutcomeSeries` fixture
covering POSITIVE, NEGATIVE, BREAKEVEN, and UNAVAILABLE outcomes (including
one signal with a 5-bar outcome but no complete 10-bar outcome), runs it
through the Phase 4A engine, and prints the resulting
`SignalInvestigationDataset` so a human can visually confirm classification
and population counts.

No network. No FastAPI/Pydantic. Run with:

    python scripts/phase4a_manual_verification.py
"""

from __future__ import annotations

from datetime import date

from app.investigation.engine import build_signal_investigation_dataset
from app.outcomes.models import SignalOutcome, SignalOutcomeSeries
from app.strategies.models import StrategyDecision

SYMBOL = "RELIANCE.NS"
INTERVAL = "1d"
STRATEGY_ID = "trend_momentum_v1"
STRATEGY_NAME = "Trend + Momentum v1"

OUTCOMES = (
    # Clearly POSITIVE.
    SignalOutcome(
        date=date(2024, 1, 5),
        decision=StrategyDecision.BUY,
        reference_close=1465.25,
        forward_close_5d=1454.20,
        forward_return_5d=-0.0075,
        forward_close_10d=1565.40,
        forward_return_10d=0.0684,
        mae_10d=-0.0189,
        mfe_10d=0.0790,
        available_forward_bars=45,
    ),
    # Clearly NEGATIVE.
    SignalOutcome(
        date=date(2024, 1, 19),
        decision=StrategyDecision.BUY,
        reference_close=1500.00,
        forward_close_5d=1480.00,
        forward_return_5d=-0.0133,
        forward_close_10d=1440.00,
        forward_return_10d=-0.0400,
        mae_10d=-0.0656,
        mfe_10d=0.0110,
        available_forward_bars=32,
    ),
    # Exact BREAKEVEN (forward_return_10d == 0.0 exactly).
    SignalOutcome(
        date=date(2024, 2, 2),
        decision=StrategyDecision.BUY,
        reference_close=1400.00,
        forward_close_5d=1410.00,
        forward_return_5d=0.0071,
        forward_close_10d=1400.00,
        forward_return_10d=0.0,
        mae_10d=-0.0250,
        mfe_10d=0.0300,
        available_forward_bars=20,
    ),
    # UNAVAILABLE: no 5D or 10D outcome at all (near end of series).
    SignalOutcome(
        date=date(2024, 6, 20),
        decision=StrategyDecision.BUY,
        reference_close=1600.00,
        forward_close_5d=None,
        forward_return_5d=None,
        forward_close_10d=None,
        forward_return_10d=None,
        mae_10d=None,
        mfe_10d=None,
        available_forward_bars=3,
    ),
    # UNAVAILABLE for the PRIMARY (10-bar) horizon despite a real 5-bar
    # outcome -- proves 5D availability never substitutes for 10D.
    SignalOutcome(
        date=date(2024, 6, 27),
        decision=StrategyDecision.BUY,
        reference_close=1610.00,
        forward_close_5d=1622.00,
        forward_return_5d=0.0075,
        forward_close_10d=None,
        forward_return_10d=None,
        mae_10d=None,
        mfe_10d=None,
        available_forward_bars=7,
    ),
)


def main() -> None:
    series = SignalOutcomeSeries(
        provider_symbol=SYMBOL, interval=INTERVAL, strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME, outcomes=OUTCOMES
    )
    dataset = build_signal_investigation_dataset(series)

    print(f"Symbol: {dataset.provider_symbol}  Strategy: {dataset.strategy_name} ({dataset.strategy_id})")
    print()
    print(f"{'Date':<12} {'Classification':<13} {'10D Return':>12} {'MAE':>10} {'MFE':>10} {'AvailBars':>10}")
    for obs in dataset.observations:
        ret = "n/a" if obs.forward_return_10d is None else f"{obs.forward_return_10d:+.4f}"
        mae = "n/a" if obs.mae_10d is None else f"{obs.mae_10d:+.4f}"
        mfe = "n/a" if obs.mfe_10d is None else f"{obs.mfe_10d:+.4f}"
        print(f"{obs.signal_date.isoformat():<12} {obs.classification.value:<13} {ret:>12} {mae:>10} {mfe:>10} {obs.available_forward_bars:>10}")

    print()
    print(f"total_signal_count:  {dataset.total_signal_count}")
    print(f"eligible_count:      {dataset.eligible_count}")
    print(f"  positive_count:    {dataset.positive_count}")
    print(f"  negative_count:    {dataset.negative_count}")
    print(f"  breakeven_count:   {dataset.breakeven_count}")
    print(f"unavailable_count:   {dataset.unavailable_count}")
    print()

    assert dataset.total_signal_count == len(OUTCOMES)
    assert dataset.eligible_count == dataset.positive_count + dataset.negative_count + dataset.breakeven_count
    assert dataset.total_signal_count == dataset.eligible_count + dataset.unavailable_count
    print("All Phase 4A population invariants hold.")


if __name__ == "__main__":
    main()

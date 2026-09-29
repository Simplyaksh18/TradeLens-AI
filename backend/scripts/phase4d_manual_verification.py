"""Phase 4D manual acceptance helper (not a test -- run manually).

Builds a deterministic synthetic OHLCV/indicator fixture and a
hand-constructed Phase 4A `SignalInvestigationDataset`, runs the REAL
accepted Phase 4A -> 4B -> 4C -> 4D pipeline (never fabricating a Phase
4B/4C result directly), prints the composed Strategy Failure
Investigation, and independently verifies that every composed value is
byte-identical to its accepted upstream source -- it does not merely
print whatever production code happens to compute.

No network. No FastAPI/Pydantic. Run with:

    cd backend
    PYTHONPATH=. python scripts/phase4d_manual_verification.py
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.indicators.models import IndicatorRow, IndicatorSeries
from app.investigation.comparison import build_failure_population_comparison
from app.investigation.composer import build_strategy_failure_investigation
from app.investigation.context import build_failure_context_dataset
from app.investigation.engine import build_signal_investigation_dataset
from app.market_data.models import OHLCVBar, OHLCVSeries
from app.outcomes.models import SignalOutcome, SignalOutcomeSeries
from app.strategies.models import StrategyDecision

SYMBOL = "RELIANCE.NS"
INTERVAL = "1d"
STRATEGY_ID = "trend_momentum_v1"
STRATEGY_NAME = "Trend + Momentum v1"

N_BARS = 30
DATES = [date(2024, 1, 1) + timedelta(days=i) for i in range(N_BARS)]
CLOSES = [1000.0 + i for i in range(N_BARS)]

ROWS: list[tuple[float, float, float]] = [(c - 10.0, c - 20.0, 55.0) for c in CLOSES]
# NEGATIVE (FAILED), indices 20-22.
ROWS[20] = (990.0, 900.0, 45.0)
ROWS[21] = (1005.0, 950.0, 50.0)
ROWS[22] = (1010.0, 990.0, 41.0)
# POSITIVE, indices 23-25.
ROWS[23] = (1000.0, 900.0, 60.0)
ROWS[24] = (1010.0, 950.0, 65.0)
ROWS[25] = (1015.0, 990.0, 58.0)
# BREAKEVEN, index 26.
ROWS[26] = (1010.0, 950.0, 55.0)
# UNAVAILABLE, index 27 -- still a valid signal-time context.
ROWS[27] = (1010.0, 950.0, 52.0)


def _market() -> OHLCVSeries:
    bars = tuple(
        OHLCVBar(date=d, open=c, high=c + 5, low=c - 5, close=c, adj_close=c, volume=1000) for d, c in zip(DATES, CLOSES)
    )
    return OHLCVSeries(provider_symbol=SYMBOL, interval=INTERVAL, bars=bars)


def _indicators() -> IndicatorSeries:
    rows = tuple(
        IndicatorRow(date=d, sma20=sma20, sma50=sma50, rsi14=rsi14, average_volume=None, volume_ratio=None)
        for d, (sma20, sma50, rsi14) in zip(DATES, ROWS)
    )
    return IndicatorSeries(provider_symbol=SYMBOL, interval=INTERVAL, rows=rows)


def _buy_outcome(index: int, forward_return_10d: float | None, mae_10d: float | None, mfe_10d: float | None) -> SignalOutcome:
    reference_close = CLOSES[index]
    present = forward_return_10d is not None
    return SignalOutcome(
        date=DATES[index],
        decision=StrategyDecision.BUY,
        reference_close=reference_close,
        forward_close_5d=reference_close * 1.01 if present else None,
        forward_return_5d=0.01 if present else None,
        forward_close_10d=reference_close * (1 + forward_return_10d) if present else None,
        forward_return_10d=forward_return_10d,
        mae_10d=mae_10d,
        mfe_10d=mfe_10d,
        available_forward_bars=15 if present else 3,
    )


def _outcome_series() -> SignalOutcomeSeries:
    outcomes = (
        _buy_outcome(20, -0.05, -0.08, 0.01),
        _buy_outcome(21, -0.02, -0.03, 0.04),
        _buy_outcome(22, -0.10, -0.12, 0.02),
        _buy_outcome(23, 0.03, -0.01, 0.05),
        _buy_outcome(24, 0.08, -0.02, 0.10),
        _buy_outcome(25, 0.01, -0.005, 0.02),
        _buy_outcome(26, 0.0, -0.015, 0.03),
        _buy_outcome(27, None, None, None),
    )
    return SignalOutcomeSeries(provider_symbol=SYMBOL, interval=INTERVAL, strategy_id=STRATEGY_ID, strategy_name=STRATEGY_NAME, outcomes=outcomes)


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:+.6f}"


def main() -> None:
    market = _market()
    indicators = _indicators()

    # Real accepted pipeline: 2A outcomes (hand-built here, standing in for
    # a real compute_signal_outcomes result) -> 4A -> 4B -> 4C -> 4D.
    outcome_series = _outcome_series()
    investigation_dataset = build_signal_investigation_dataset(outcome_series)
    outcome_comparison = build_failure_population_comparison(investigation_dataset)
    context_analysis = build_failure_context_dataset(investigation_dataset, market, indicators)
    investigation = build_strategy_failure_investigation(investigation_dataset, outcome_comparison, context_analysis)

    print("STRATEGY FAILURE INVESTIGATION")
    print()
    print("METADATA")
    print(f"  symbol:        {investigation.provider_symbol}")
    print(f"  interval:      {investigation.interval}")
    print(f"  strategy:      {investigation.strategy_id}")
    print(f"  strategy name: {investigation.strategy_name}")
    print()

    print("POPULATION")
    print(f"  total:        {investigation.total_signal_count}")
    print(f"  eligible:     {investigation.eligible_count}")
    print(f"  failed:       {investigation.failed_count}")
    print(f"  non_failed:   {investigation.non_failed_count}")
    print(f"  unavailable:  {investigation.unavailable_count}")
    print()

    def print_outcome(label: str, summary) -> None:
        print(f"  {label}")
        print(f"    count:                {summary.count}")
        print(f"    average 10D return:   {_fmt(summary.average_forward_return_10d)}")
        print(f"    median 10D return:    {_fmt(summary.median_forward_return_10d)}")
        print(f"    average MAE:          {_fmt(summary.average_mae_10d)}")
        print(f"    median MAE:           {_fmt(summary.median_mae_10d)}")
        print(f"    worst MAE:            {_fmt(summary.worst_mae_10d)}")
        print(f"    average MFE:          {_fmt(summary.average_mfe_10d)}")
        print(f"    median MFE:           {_fmt(summary.median_mfe_10d)}")
        print(f"    best MFE:             {_fmt(summary.best_mfe_10d)}")

    print("OUTCOME COMPARISON")
    print_outcome("FAILED", investigation.outcome_comparison.failed)
    print_outcome("NON_FAILED", investigation.outcome_comparison.non_failed)
    print()

    def print_context(label: str, summary) -> None:
        print(f"  {label}")
        print(f"    RSI avg/median:             {_fmt(summary.average_rsi14)} / {_fmt(summary.median_rsi14)}")
        print(f"    volatility avail/unavail:   {summary.volatility_available_count}/{summary.volatility_unavailable_count}")
        print(f"    volatility avg/median:      {_fmt(summary.average_annualized_realized_volatility_20)} / {_fmt(summary.median_annualized_realized_volatility_20)}")
        print(f"    close/SMA20 avg/median:     {_fmt(summary.average_close_above_sma20_fraction)} / {_fmt(summary.median_close_above_sma20_fraction)}")
        print(f"    SMA20/SMA50 avg/median:     {_fmt(summary.average_sma20_above_sma50_fraction)} / {_fmt(summary.median_sma20_above_sma50_fraction)}")
        print(
            f"    regime counts (bull/bear/trans/insuf): {summary.bullish_trend_count}/{summary.bearish_trend_count}/"
            f"{summary.transitional_count}/{summary.insufficient_data_count}"
        )

    print("SIGNAL-TIME CONTEXT COMPARISON")
    print_context("FAILED", investigation.context_analysis.failed)
    print_context("NON_FAILED", investigation.context_analysis.non_failed)
    print()

    print("TRACEABILITY (first 5 observations)")
    for ctx in investigation.context_analysis.observations[:5]:
        print(f"  {ctx.signal_date.isoformat()}  {ctx.classification.value}")
    print()

    # --- Independent verification -------------------------------------

    assert investigation.provider_symbol == investigation_dataset.provider_symbol == SYMBOL
    assert investigation.interval == investigation_dataset.interval == INTERVAL
    assert investigation.strategy_id == investigation_dataset.strategy_id == STRATEGY_ID
    assert investigation.strategy_name == investigation_dataset.strategy_name == STRATEGY_NAME
    print("Metadata matches Phase 4A exactly.")

    assert investigation.total_signal_count == investigation_dataset.total_signal_count == 8
    assert investigation.failed_count == investigation_dataset.negative_count == 3
    assert investigation.non_failed_count == investigation_dataset.positive_count + investigation_dataset.breakeven_count == 4
    assert investigation.unavailable_count == investigation_dataset.unavailable_count == 1
    assert investigation.eligible_count == investigation.failed_count + investigation.non_failed_count == 7
    print("Population counts match the accepted Phase 4A source exactly.")

    assert investigation.outcome_comparison == outcome_comparison
    assert investigation.outcome_comparison is outcome_comparison
    print("Outcome comparison is the exact accepted Phase 4B result (by identity).")

    assert investigation.context_analysis == context_analysis
    assert investigation.context_analysis is context_analysis
    print("Context analysis is the exact accepted Phase 4C result (by identity).")

    expected_sequence = [(o.signal_date, o.classification) for o in investigation_dataset.observations]
    actual_sequence = [(o.signal_date, o.classification) for o in investigation.context_analysis.observations]
    assert expected_sequence == actual_sequence
    print("Observation date/classification sequence unchanged between Phase 4A and the composed result.")

    rebuilt = build_strategy_failure_investigation(investigation_dataset, outcome_comparison, context_analysis)
    assert rebuilt == investigation
    print("Deterministic rebuild produced an identical result.")

    print()
    print("ALL MANUAL PHASE 4D CHECKS PASSED")


if __name__ == "__main__":
    main()
